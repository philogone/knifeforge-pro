import paper from "paper";

import { UI_COLOR } from "./constants";
import { arcThrough, circleThrough, dragCurvePoint, mirrorNode, symmetricComplete } from "./drafting";
import { formatMm, type EditorEngine, type Mods } from "./engine";
import type { DocNode, ToolName } from "./types";
import { RULER_SIZE } from "./view";

export interface ToolHandler {
  cursor: string;
  /** i18n key shown in the status bar */
  hint: string;
  down(p: paper.Point, m: Mods): void;
  drag(p: paper.Point, m: Mods): void;
  up(p: paper.Point, m: Mods): void;
  move(p: paper.Point, m: Mods): void;
  doubleClick(p: paper.Point, m: Mods): void;
  /** returns true when the key was consumed */
  key(key: string): boolean;
  cancel(): void;
  drawOverlay(): void;
  /** typed length (mm) and angle (degrees, counter-clockwise, y up); true when used */
  numeric?(length: number, angle: number): boolean;
}

function nodesOf(path: paper.Path): DocNode[] {
  return path.segments.map((sg) => ({ x: sg.point.x, y: sg.point.y, ix: sg.handleIn.x, iy: sg.handleIn.y, ox: sg.handleOut.x, oy: sg.handleOut.y }));
}

/** Point `length` away from `from` in the direction `angle` (degrees, counter-clockwise, y up). */
function polar(from: paper.Point, length: number, angle: number): paper.Point {
  const rad = (angle * Math.PI) / 180;
  return new paper.Point(Math.round((from.x + length * Math.cos(rad)) * 10000) / 10000, Math.round((from.y - length * Math.sin(rad)) * 10000) / 10000);
}

abstract class BaseTool implements ToolHandler {
  cursor = "default";
  hint = "";
  constructor(protected e: EditorEngine) {}
  down(_p: paper.Point, _m: Mods): void {}
  drag(_p: paper.Point, _m: Mods): void {}
  up(_p: paper.Point, _m: Mods): void {}
  move(_p: paper.Point, _m: Mods): void {}
  doubleClick(_p: paper.Point, _m: Mods): void {}
  key(_key: string): boolean {
    return false;
  }
  cancel(): void {}
  drawOverlay(): void {}

  protected uiStroke(item: paper.Item, dash = false): paper.Item {
    item.strokeColor = new paper.Color(UI_COLOR);
    item.strokeWidth = 1;
    item.strokeScaling = false;
    if (dash) item.dashArray = [4, 3];
    return item;
  }

  /** Doc item under the cursor (resolved to the top-level item of its layer). */
  protected hitItem(p: paper.Point, tolerancePx = 5): paper.Item | null {
    const hit = this.e.project.hitTest(p, {
      fill: true,
      stroke: true,
      tolerance: this.e.px(tolerancePx),
      match: (h: paper.HitResult) => !!this.topItem(h.item),
    });
    return hit ? this.topItem(hit.item) : null;
  }

  protected topItem(item: paper.Item): paper.Item | null {
    let cur: paper.Item | null = item;
    while (cur && cur.parent) {
      if (cur.parent.data?.layerId) return cur.layer === this.e.ui ? null : cur;
      cur = cur.parent as paper.Item;
    }
    return null;
  }

  protected activeLayerUsable(): boolean {
    const meta = this.e.layerMeta(this.e.activeLayerId);
    if (!meta || meta.locked || !meta.visible) {
      this.e.hint("hint.layerLocked");
      return false;
    }
    return true;
  }
}

// ---------------------------------------------------------------------------
// Select / transform
// ---------------------------------------------------------------------------

const HANDLE_NAMES = ["tl", "tm", "tr", "mr", "br", "bm", "bl", "ml"] as const;
type HandleName = (typeof HANDLE_NAMES)[number] | "rot";

class SelectTool extends BaseTool {
  cursor = "default";
  hint = "hint.select";
  private mode: "none" | "move" | "scale" | "rotate" | "band" | "guide" = "none";
  private guideIndex = -1;
  private start = new paper.Point(0, 0);
  private last = new paper.Point(0, 0);
  private startBounds: paper.Rectangle | null = null;
  private changed = false;
  private handle: HandleName | null = null;
  private anchor = new paper.Point(0, 0);
  private rotCenter = new paper.Point(0, 0);
  private rotApplied = 0;
  private band: paper.Path | null = null;
  private clickedSelected = false;

  down(p: paper.Point, m: Mods): void {
    this.start = p.clone();
    this.last = p.clone();
    this.changed = false;
    this.clickedSelected = false;

    const handle = this.hitHandle(p);
    if (handle && this.e.selection.length) {
      this.handle = handle;
      this.startBounds = this.e.selectionBounds();
      if (handle === "rot") {
        this.mode = "rotate";
        this.rotCenter = this.startBounds!.center;
        this.rotApplied = 0;
      } else {
        this.mode = "scale";
        this.anchor = this.anchorFor(handle, this.startBounds!);
      }
      return;
    }

    const item = this.hitItem(p);
    if (item) {
      if (m.shift) {
        this.e.addToSelection(item);
        this.mode = "none";
        return;
      }
      if (!this.e.selection.includes(item)) this.e.selectItems([item]);
      else this.clickedSelected = true;
      this.mode = "move";
      this.startBounds = this.e.selectionBounds();
      return;
    }
    const guide = this.e.guideAt(p);
    if (guide >= 0) {
      this.guideIndex = guide;
      this.mode = "guide";
      return;
    }
    if (!m.shift) this.e.selectItems([]);
    this.mode = "band";
  }

  drag(p: paper.Point, m: Mods): void {
    if (this.mode === "move" && this.startBounds) {
      const raw = p.subtract(this.start);
      if (!this.changed && raw.length < this.e.px(2)) return;
      const snapped = this.snapMove(raw, m);
      const current = this.e.selectionBounds()!;
      const delta = this.startBounds.topLeft.add(snapped).subtract(current.topLeft);
      if (delta.length > 0) {
        for (const item of this.e.selection) item.translate(delta);
        this.changed = true;
      }
      this.e.refreshOverlay();
      this.e.emitSelection();
    } else if (this.mode === "scale" && this.startBounds && this.handle && this.handle !== "rot") {
      this.doScale(m.alt ? p : this.e.snap(p), m);
    } else if (this.mode === "rotate" && this.startBounds) {
      this.doRotate(p, m);
    } else if (this.mode === "band") {
      this.band?.remove();
      this.band = new paper.Path.Rectangle({ from: this.start, to: p, insert: false });
      this.uiStroke(this.band, true);
      this.band.fillColor = new paper.Color(79 / 255, 70 / 255, 229 / 255, 0.08);
      this.e.addUi(this.band, "band");
    } else if (this.mode === "guide") {
      const g = this.e.guides[this.guideIndex];
      if (g) {
        const pos = this.e.snapAxis(g.axis === "x" ? p.x : p.y);
        this.e.moveGuide(this.guideIndex, pos, false);
        this.e.hintValue(`${g.axis === "x" ? "X" : "Y"} = ${formatMm(pos)} mm`);
      }
    }
    this.last = p.clone();
  }

  up(p: paper.Point, m: Mods): void {
    if (this.mode === "guide") {
      // dropped back on a ruler = deleted (as in Inkscape); otherwise one undo step for the move
      if (this.e.overRuler(p, RULER_SIZE)) this.e.removeGuide(this.guideIndex);
      else if (p.getDistance(this.start) > 1e-9) this.e.commit();
      this.e.hintValue("");
      this.mode = "none";
      this.guideIndex = -1;
      return;
    }
    if (this.mode === "band") {
      this.band?.remove();
      this.band = null;
      this.e.clearUi("band");
      const rect = new paper.Rectangle(this.start, p);
      if (rect.width > this.e.px(3) || rect.height > this.e.px(3)) {
        const picked = this.e.docItems().filter((i) => i.visible && !i.parent?.locked && (m.alt ? i.bounds.intersects(rect) : rect.contains(i.bounds)));
        this.e.selectItems(m.shift ? [...new Set([...this.e.selection, ...picked])] : picked);
      }
    } else if (this.mode === "move" && !this.changed && this.clickedSelected) {
      // a plain click on an already-selected item narrows the selection to it
      const item = this.hitItem(p);
      if (item && this.e.selection.length > 1) this.e.selectItems([item]);
    }
    if (this.changed) this.e.commit();
    this.e.clearUi("snap");
    this.mode = "none";
    this.handle = null;
  }

  move(p: paper.Point): void {
    const guide = this.e.guideAt(p);
    const axis = guide >= 0 ? this.e.guides[guide].axis : null;
    this.e.canvas.style.cursor = this.hitHandle(p)
      ? "crosshair"
      : this.hitItem(p)
        ? "move"
        : axis === "x"
          ? "ew-resize"
          : axis === "y"
            ? "ns-resize"
            : "default";
  }

  doubleClick(p: paper.Point): void {
    const item = this.hitItem(p);
    if (item && item.data?.kind !== "dim") {
      this.e.selectItems([item]);
      this.e.setTool("node");
    }
  }

  key(key: string): boolean {
    if (key === "Escape") {
      this.e.selectItems([]);
      return true;
    }
    return false;
  }

  cancel(): void {
    this.band?.remove();
    this.band = null;
    this.e.clearUi("band");
    this.mode = "none";
  }

  private snapMove(raw: paper.Point, m: Mods): paper.Point {
    const b = this.startBounds!;
    if (m.alt) return raw;
    this.e.clearUi("snap");
    const anchors = [b.topLeft, b.topRight, b.bottomLeft, b.bottomRight, b.center];
    if (this.e.snapToNodes) {
      let best: paper.Point | null = null;
      let bestDist = this.e.px(10);
      let marker: paper.Point | null = null;
      for (const a of anchors) {
        const moved = a.add(raw);
        const node = this.e.nearestNode(moved, bestDist, this.e.selection);
        if (node) {
          const offset = node.subtract(moved);
          if (offset.length < bestDist) {
            bestDist = offset.length;
            best = offset;
            marker = node;
          }
        }
      }
      if (best && marker) {
        this.e.showSnapMarker(marker);
        return raw.add(best);
      }
    }
    if (this.e.snapToGrid) {
      const g = this.e.gridSize;
      const tl = b.topLeft.add(raw);
      return raw.add(new paper.Point(Math.round(tl.x / g) * g - tl.x, Math.round(tl.y / g) * g - tl.y));
    }
    return raw;
  }

  private doScale(p: paper.Point, m: Mods): void {
    const start = this.startBounds!;
    const cur = this.e.selectionBounds()!;
    const h = this.handle as Exclude<HandleName, "rot">;
    const hp = this.handlePoint(h, start);
    let sx = 1;
    let sy = 1;
    if (h.includes("l") || h.includes("r")) {
      const denom = hp.x - this.anchor.x;
      sx = Math.abs(denom) > 1e-9 ? (p.x - this.anchor.x) / denom : 1;
    }
    if (h.includes("t") || h.includes("b")) {
      const denom = hp.y - this.anchor.y;
      sy = Math.abs(denom) > 1e-9 ? (p.y - this.anchor.y) / denom : 1;
    }
    const isCorner = h.length === 2 && h[0] !== "m" && h[1] !== "m";
    if (m.shift && isCorner) {
      const s = Math.max(Math.abs(sx), Math.abs(sy));
      sx = s;
      sy = s;
    }
    const minScale = 0.01;
    sx = Math.max(minScale, sx);
    sy = Math.max(minScale, sy);
    const targetW = start.width * sx;
    const targetH = start.height * sy;
    const stepX = cur.width > 1e-9 ? targetW / cur.width : 1;
    const stepY = cur.height > 1e-9 ? targetH / cur.height : 1;
    if (Math.abs(stepX - 1) < 1e-9 && Math.abs(stepY - 1) < 1e-9) return;
    for (const item of this.e.selection) item.scale(stepX, stepY, this.anchor);
    this.changed = true;
    this.e.refreshOverlay();
    this.e.emitSelection();
  }

  private doRotate(p: paper.Point, m: Mods): void {
    const a0 = Math.atan2(this.start.y - this.rotCenter.y, this.start.x - this.rotCenter.x);
    const a1 = Math.atan2(p.y - this.rotCenter.y, p.x - this.rotCenter.x);
    let total = ((a1 - a0) * 180) / Math.PI;
    if (m.shift) total = Math.round(total / 15) * 15;
    const step = total - this.rotApplied;
    if (Math.abs(step) < 1e-9) return;
    for (const item of this.e.selection) item.rotate(step, this.rotCenter);
    this.rotApplied = total;
    this.changed = true;
    this.e.refreshOverlay();
    this.e.emitSelection();
  }

  private handlePoint(h: Exclude<HandleName, "rot">, b: paper.Rectangle): paper.Point {
    const x = h.includes("l") ? b.left : h.includes("r") ? b.right : b.center.x;
    const y = h.includes("t") ? b.top : h.includes("b") ? b.bottom : b.center.y;
    return new paper.Point(x, y);
  }

  private anchorFor(h: HandleName, b: paper.Rectangle): paper.Point {
    const x = h.includes("l") ? b.right : h.includes("r") ? b.left : b.center.x;
    const y = h.includes("t") ? b.bottom : h.includes("b") ? b.top : b.center.y;
    return new paper.Point(x, y);
  }

  private hitHandle(p: paper.Point): HandleName | null {
    const hit = this.e.ui.hitTest(p, { fill: true, stroke: true, tolerance: this.e.px(3), match: (h: paper.HitResult) => !!h.item.data?.handle });
    return hit ? (hit.item.data.handle as HandleName) : null;
  }

  drawOverlay(): void {
    drawSelectionOverlay(this.e, true);
  }
}

export function drawSelectionOverlay(e: EditorEngine, withHandles: boolean): void {
  const sel = e.selection;
  if (!sel.length) return;
  for (const item of sel) {
    const outline = item.clone({ insert: false, deep: true });
    outline.data = {};
    outline.fillColor = null;
    outline.strokeColor = new paper.Color(UI_COLOR);
    outline.strokeWidth = 2;
    outline.strokeScaling = false;
    outline.dashArray = [];
    // text / arrows inside a dimension keep their own look; outline only the strokes
    if (item.data?.kind === "dim") outline.opacity = 0.9;
    e.addUi(outline, "sel");
  }
  const b = e.selectionBounds();
  if (!b || !withHandles) return;
  const box = new paper.Path.Rectangle({ rectangle: b, insert: false });
  box.strokeColor = new paper.Color(UI_COLOR);
  box.strokeWidth = 1;
  box.strokeScaling = false;
  box.dashArray = [4, 3];
  box.fillColor = null;
  box.data = {};
  e.addUi(box, "sel");
  const size = e.px(8);
  const pts: Record<(typeof HANDLE_NAMES)[number], paper.Point> = {
    tl: b.topLeft,
    tm: new paper.Point(b.center.x, b.top),
    tr: b.topRight,
    mr: new paper.Point(b.right, b.center.y),
    br: b.bottomRight,
    bm: new paper.Point(b.center.x, b.bottom),
    bl: b.bottomLeft,
    ml: new paper.Point(b.left, b.center.y),
  };
  for (const name of HANDLE_NAMES) {
    const sq = new paper.Path.Rectangle({ center: pts[name], size: [size, size], insert: false });
    sq.fillColor = new paper.Color("#ffffff");
    sq.strokeColor = new paper.Color(UI_COLOR);
    sq.strokeWidth = 1;
    sq.strokeScaling = false;
    sq.data = { handle: name };
    e.addUi(sq, "sel");
  }
  const rotPoint = new paper.Point(b.center.x, b.top - e.px(22));
  const stem = new paper.Path.Line({ from: new paper.Point(b.center.x, b.top), to: rotPoint, insert: false });
  stem.strokeColor = new paper.Color(UI_COLOR);
  stem.strokeWidth = 1;
  stem.strokeScaling = false;
  stem.data = {};
  e.addUi(stem, "sel");
  const rot = new paper.Path.Circle({ center: rotPoint, radius: e.px(5), insert: false });
  rot.fillColor = new paper.Color(UI_COLOR);
  rot.data = { handle: "rot" };
  e.addUi(rot, "sel");
}

// ---------------------------------------------------------------------------
// Node editing
// ---------------------------------------------------------------------------

type NodeHit = { kind: "node" | "handleIn" | "handleOut"; seg: paper.Segment };

class NodeTool extends BaseTool {
  cursor = "default";
  hint = "hint.node";
  private mode: "none" | "nodes" | "handle" | "band" | "curve" = "none";
  /** segment being bent by dragging its middle: its two nodes, the grabbed time and the start state */
  private curve: { a: paper.Segment; b: paper.Segment; t: number; out0: paper.Point; in0: paper.Point } | null = null;
  private hit: NodeHit | null = null;
  private start = new paper.Point(0, 0);
  private last = new paper.Point(0, 0);
  private changed = false;
  private wasSmooth = false;
  private oppLength = 0;
  private band: paper.Path | null = null;

  down(p: paper.Point, m: Mods): void {
    this.start = p.clone();
    this.last = p.clone();
    this.changed = false;
    const hit = this.hitNode(p);
    if (hit) {
      this.hit = hit;
      if (hit.kind === "node") {
        const selected = this.e.selectedSegments;
        if (m.shift) {
          this.e.selectedSegments = selected.includes(hit.seg) ? selected.filter((s) => s !== hit.seg) : [...selected, hit.seg];
        } else if (!selected.includes(hit.seg)) {
          this.e.selectedSegments = [hit.seg];
        }
        this.mode = "nodes";
      } else {
        this.mode = "handle";
        const seg = hit.seg;
        this.wasSmooth = this.e.isSmooth(seg);
        this.oppLength = (hit.kind === "handleOut" ? seg.handleIn : seg.handleOut).length;
      }
      this.e.refreshOverlay();
      this.e.emitSelection();
      return;
    }
    // press on a segment of an edited path (or of any path, which it then edits): bend it
    const onCurve = this.hitCurve(p);
    if (onCurve) {
      const path = onCurve.path;
      const top = this.topItem(path);
      if (!this.e.nodeTargets.includes(path) && top) this.e.selectItems(m.shift ? [...this.e.selection, top] : [top]);
      if (this.e.nodeTargets.includes(path)) {
        const { a, b, t } = onCurve;
        // only this segment's two inner handles move: the neighbouring segments are never touched,
        // so a smooth end may become a corner (Inkscape would rotate the other handle instead)
        this.curve = { a, b, t, out0: a.handleOut.clone(), in0: b.handleIn.clone() };
        if (!m.shift) this.e.selectedSegments = [];
        this.mode = "curve";
        this.e.refreshOverlay();
        this.e.emitSelection();
        return;
      }
    }
    const item = this.hitItem(p);
    if (item && item.data?.kind !== "dim") {
      if (!this.e.selection.includes(item)) this.e.selectItems(m.shift ? [...this.e.selection, item] : [item]);
      this.mode = "none";
      return;
    }
    if (!m.shift) {
      this.e.selectedSegments = [];
      this.e.emitSelection();
    }
    this.mode = "band";
  }

  drag(p: paper.Point, m: Mods): void {
    if (this.mode === "nodes") {
      const segs = this.e.selectedSegments;
      if (!segs.length) return;
      if (!this.changed && p.subtract(this.start).length < this.e.px(2)) return;
      if (segs.length === 1 && !m.alt) {
        segs[0].point = this.e.snap(p, [], { skipSegments: [segs[0]], skipPaths: [segs[0].path] });
      } else {
        const delta = p.subtract(this.last);
        for (const s of segs) s.point = s.point.add(delta);
      }
      this.changed = true;
    } else if (this.mode === "handle" && this.hit) {
      const seg = this.hit.seg;
      let vec = p.subtract(seg.point);
      if (m.shift) {
        const ang = Math.round(vec.angle / 15) * 15;
        vec = new paper.Point({ length: vec.length, angle: ang });
      }
      if (this.hit.kind === "handleOut") {
        seg.handleOut = vec;
        if (this.wasSmooth && !m.alt && vec.length > 1e-9) seg.handleIn = vec.normalize(-this.oppLength);
      } else {
        seg.handleIn = vec;
        if (this.wasSmooth && !m.alt && vec.length > 1e-9) seg.handleOut = vec.normalize(-this.oppLength);
      }
      this.changed = true;
    } else if (this.mode === "curve" && this.curve) {
      if (!this.changed && p.subtract(this.start).length < this.e.px(2)) return;
      const { a, b, t, out0, in0 } = this.curve;
      const P = (q: paper.Point): [number, number] => [q.x, q.y];
      const delta = p.subtract(this.start);
      const [c1, c2] = dragCurvePoint(P(a.point), P(a.point.add(out0)), P(b.point.add(in0)), P(b.point), t, [delta.x, delta.y]);
      a.handleOut = new paper.Point(c1[0], c1[1]).subtract(a.point);
      b.handleIn = new paper.Point(c2[0], c2[1]).subtract(b.point);
      this.changed = true;
      this.e.canvas.style.cursor = "grabbing";
    } else if (this.mode === "band") {
      this.band?.remove();
      this.band = new paper.Path.Rectangle({ from: this.start, to: p, insert: false });
      this.uiStroke(this.band, true);
      this.band.fillColor = new paper.Color(79 / 255, 70 / 255, 229 / 255, 0.08);
      this.e.addUi(this.band, "band");
    }
    this.last = p.clone();
    this.e.refreshOverlay();
    this.e.emitSelection();
  }

  up(p: paper.Point, m: Mods): void {
    if (this.mode === "band") {
      this.band?.remove();
      this.band = null;
      this.e.clearUi("band");
      const rect = new paper.Rectangle(this.start, p);
      if (rect.width > this.e.px(3) || rect.height > this.e.px(3)) {
        const inside = this.e.nodeTargets.flatMap((path) => path.segments.filter((s) => rect.contains(s.point)));
        this.e.selectedSegments = m.shift ? [...new Set([...this.e.selectedSegments, ...inside])] : inside;
      }
      this.e.refreshOverlay();
      this.e.emitSelection();
    }
    if (this.changed) this.e.commit();
    this.e.clearUi("snap");
    this.mode = "none";
    this.hit = null;
    this.curve = null;
  }

  move(p: paper.Point): void {
    const hit = this.hitNode(p);
    this.e.canvas.style.cursor = hit ? "pointer" : this.hitCurve(p) ? "grab" : "default";
  }

  /** Segment of a path under the pointer (away from its nodes), with the time along it. */
  private hitCurve(p: paper.Point): { path: paper.Path; a: paper.Segment; b: paper.Segment; t: number } | null {
    const found = this.e.project.hitTest(p, {
      stroke: true,
      tolerance: this.e.px(5),
      match: (h: paper.HitResult) => {
        const top = h.item instanceof paper.Path ? this.topItem(h.item) : null;
        return !!top && top.data?.kind !== "dim" && !this.e.layerMeta(top.parent?.data?.layerId)?.locked;
      },
    });
    const loc = found?.location;
    if (!loc?.curve || !(found.item instanceof paper.Path)) return null;
    return { path: found.item, a: loc.curve.segment1, b: loc.curve.segment2, t: loc.time };
  }

  doubleClick(p: paper.Point): void {
    const hit = this.hitNode(p);
    if (hit?.kind === "node") {
      this.e.selectedSegments = [hit.seg];
      this.e.setNodeType(this.e.isSmooth(hit.seg) ? "corner" : "smooth");
      return;
    }
    // double-click on a curve of an edited path inserts a node there
    const found = this.e.project.hitTest(p, { stroke: true, tolerance: this.e.px(6), match: (h: paper.HitResult) => this.e.nodeTargets.includes(h.item as paper.Path) });
    if (found?.location && found.item instanceof paper.Path) {
      const seg = found.item.divideAt(found.location);
      if (seg) {
        this.e.selectedSegments = [seg];
        this.e.commit();
      }
    }
  }

  key(key: string): boolean {
    if (key === "Delete" || key === "Backspace") {
      this.e.deleteSelectedNodes();
      return true;
    }
    if (key === "Escape") {
      if (this.e.selectedSegments.length) {
        this.e.selectedSegments = [];
        this.e.refreshOverlay();
        this.e.emitSelection();
      } else {
        this.e.setTool("select");
      }
      return true;
    }
    return false;
  }

  cancel(): void {
    this.band?.remove();
    this.band = null;
    this.e.clearUi("band");
    this.mode = "none";
    this.curve = null;
  }

  private hitNode(p: paper.Point): NodeHit | null {
    const r = this.e.px(7);
    for (const seg of this.e.selectedSegments) {
      if (seg.handleOut.length > 1e-6 && seg.point.add(seg.handleOut).getDistance(p) < r) return { kind: "handleOut", seg };
      if (seg.handleIn.length > 1e-6 && seg.point.add(seg.handleIn).getDistance(p) < r) return { kind: "handleIn", seg };
    }
    let best: NodeHit | null = null;
    let bestDist = r;
    for (const path of this.e.nodeTargets) {
      for (const seg of path.segments) {
        const d = seg.point.getDistance(p);
        if (d < bestDist) {
          bestDist = d;
          best = { kind: "node", seg };
        }
      }
    }
    return best;
  }

  drawOverlay(): void {
    const e = this.e;
    for (const path of e.nodeTargets) {
      if (!path.parent) continue;
      const outline = path.clone({ insert: false });
      outline.data = {};
      outline.fillColor = null;
      outline.strokeColor = new paper.Color(UI_COLOR);
      outline.strokeWidth = 1.5;
      outline.strokeScaling = false;
      outline.dashArray = [];
      e.addUi(outline, "nodes");
    }
    const size = e.px(7);
    for (const path of e.nodeTargets) {
      for (const seg of path.segments) {
        const selected = e.selectedSegments.includes(seg);
        if (selected) {
          for (const [handle, tag] of [[seg.handleIn, "in"], [seg.handleOut, "out"]] as const) {
            if (handle.length < 1e-6) continue;
            const tip = seg.point.add(handle);
            const line = new paper.Path.Line({ from: seg.point, to: tip, insert: false });
            line.strokeColor = new paper.Color("#64748b");
            line.strokeWidth = 1;
            line.strokeScaling = false;
            line.data = {};
            e.addUi(line, "nodes");
            const dot = new paper.Path.Circle({ center: tip, radius: e.px(4), insert: false });
            dot.fillColor = new paper.Color("#ffffff");
            dot.strokeColor = new paper.Color("#64748b");
            dot.strokeWidth = 1;
            dot.strokeScaling = false;
            dot.data = { handleTag: tag };
            e.addUi(dot, "nodes");
          }
        }
        const smooth = e.isSmooth(seg);
        const marker = smooth
          ? new paper.Path.Circle({ center: seg.point, radius: size / 2, insert: false })
          : new paper.Path.Rectangle({ center: seg.point, size: [size, size], insert: false });
        marker.fillColor = new paper.Color(selected ? UI_COLOR : "#ffffff");
        marker.strokeColor = new paper.Color(UI_COLOR);
        marker.strokeWidth = 1.5;
        marker.strokeScaling = false;
        marker.data = {};
        e.addUi(marker, "nodes");
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Pen (Bézier)
// ---------------------------------------------------------------------------

class PenTool extends BaseTool {
  cursor = "crosshair";
  hint = "hint.pen";
  private path: paper.Path | null = null;
  private dragging = false;
  private rubber: paper.Path | null = null;

  down(p: paper.Point, m: Mods): void {
    if (!this.path && !this.activeLayerUsable()) return;
    const pt = this.e.snap(p, [], { from: this.path?.lastSegment?.point, constrain: m.shift });
    if (!this.path) {
      this.path = new paper.Path({ insert: false });
      this.path.strokeColor = new paper.Color(UI_COLOR);
      this.path.strokeWidth = 1.5;
      this.path.strokeScaling = false;
      this.e.addUi(this.path, "pen");
      this.path.add(pt);
      this.dragging = true;
      this.e.emit("drawing", true);
      return;
    }
    if (this.path.segments.length >= 2 && this.path.firstSegment.point.getDistance(p) < this.e.px(9)) {
      this.path.closed = true;
      this.finish();
      return;
    }
    this.path.add(pt);
    this.dragging = true;
  }

  drag(p: paper.Point, m: Mods): void {
    if (!this.path || !this.dragging) return;
    const seg = this.path.lastSegment;
    const handle = p.subtract(seg.point);
    seg.handleOut = handle;
    seg.handleIn = handle.multiply(-1);
    this.drawRubber(p, m);
  }

  up(): void {
    this.dragging = false;
  }

  move(p: paper.Point, m: Mods): void {
    this.drawRubber(p, m);
    if (this.path && this.path.segments.length >= 2) {
      this.e.canvas.style.cursor = this.path.firstSegment.point.getDistance(p) < this.e.px(9) ? "pointer" : "crosshair";
    }
  }

  doubleClick(): void {
    if (!this.path) return;
    // the second click of a double-click already added a duplicate point
    const segs = this.path.segments;
    if (segs.length >= 2 && segs[segs.length - 1].point.getDistance(segs[segs.length - 2].point) < this.e.px(4)) {
      this.path.removeSegment(segs.length - 1);
    }
    this.finish();
  }

  key(key: string): boolean {
    if (key === "Enter") {
      this.finish();
      return true;
    }
    if (key === "Escape") {
      this.cancel();
      return true;
    }
    if (key === "Backspace" && this.path) {
      if (this.path.segments.length > 1) this.path.removeSegment(this.path.segments.length - 1);
      else this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    const was = !!this.path;
    this.path?.remove();
    this.path = null;
    this.rubber?.remove();
    this.rubber = null;
    this.dragging = false;
    this.e.clearUi("pen");
    this.e.clearUi("rubber");
    this.e.clearUi("mirror");
    if (was) this.e.emit("drawing", false);
  }

  /** Next node at a typed distance and angle from the last one. */
  numeric(length: number, angle: number): boolean {
    if (!this.path || !this.path.segments.length || !(length > 0)) return false;
    this.path.add(polar(this.path.lastSegment.point, length, angle));
    this.drawMirror();
    return true;
  }

  /** Live mirror image of what is drawn so far (symmetry mode). */
  private drawMirror(extra?: paper.Point): void {
    this.e.clearUi("mirror");
    const ax = this.e.symmetry;
    if (!ax || !this.path) return;
    const nodes = nodesOf(this.path);
    if (extra) nodes.push({ x: extra.x, y: extra.y, ix: 0, iy: 0, ox: 0, oy: 0 });
    if (nodes.length < 2) return;
    const ghost = this.e.contourToPath(nodes.map((n) => mirrorNode(n, ax)), false);
    this.uiStroke(ghost, true);
    ghost.strokeColor = new paper.Color("#c026d3");
    this.e.addUi(ghost, "mirror");
  }

  private drawRubber(p: paper.Point, m: Mods = { shift: false, alt: false, ctrl: false }): void {
    this.rubber?.remove();
    this.rubber = null;
    if (!this.path || this.path.segments.length === 0 || this.dragging) return;
    const last = this.path.lastSegment;
    const rubber = new paper.Path({ insert: false });
    rubber.add(new paper.Segment(last.point, undefined, last.handleOut));
    const end = this.e.snap(p, [], { from: last.point, constrain: m.shift });
    rubber.add(end);
    const v = end.subtract(last.point);
    this.e.hintValue(`${formatMm(v.length)} mm · ${Math.round(-v.angle * 10) / 10}°`);
    this.drawMirror(end);
    this.uiStroke(rubber, true);
    this.rubber = rubber;
    this.e.addUi(rubber, "rubber");
  }

  private finish(): void {
    const path = this.path;
    this.path = null;
    this.rubber?.remove();
    this.rubber = null;
    this.e.clearUi("rubber");
    if (!path || path.segments.length < 2) {
      path?.remove();
      return;
    }
    this.e.clearUi("mirror");
    this.e.emit("drawing", false);
    path.data = {};
    const ax = this.e.symmetry;
    if (ax && !path.closed) {
      // a half outline: closed with its mirror when both ends touch the axis, else mirrored apart
      const done = symmetricComplete(nodesOf(path), ax, this.e.px(9));
      path.remove();
      this.e.clearUi("pen");
      const items: paper.Item[] = [];
      if ("closed" in done) {
        items.push(this.e.addItem(this.e.contourToPath(done.closed, true)));
      } else {
        items.push(this.e.addItem(this.e.contourToPath(nodesOf(path), false)));
        items.push(this.e.addItem(this.e.contourToPath(done.mirror, false)));
        if (this.e.roleOf(items[0]) === "cut") this.e.hint("hint.openCutPath");
      }
      this.e.selectItems(items);
      this.e.commit();
      return;
    }
    this.e.addItem(path, { select: false });
    if (!path.closed && this.e.roleOf(path) === "cut") this.e.hint("hint.openCutPath");
    this.e.clearUi("pen");
    this.e.selectItems([path]);
    this.e.commit();
  }
}

// ---------------------------------------------------------------------------
// Shapes: rectangle, ellipse, line, regular polygon
// ---------------------------------------------------------------------------

class ShapeTool extends BaseTool {
  cursor = "crosshair";
  hint: string;
  private start: paper.Point | null = null;
  private preview: paper.Path | null = null;

  constructor(
    e: EditorEngine,
    private kind: "rect" | "ellipse" | "line" | "polygon",
  ) {
    super(e);
    this.hint = `hint.${kind}`;
  }

  down(p: paper.Point): void {
    if (!this.activeLayerUsable()) return;
    this.start = this.e.snap(p);
  }

  drag(p: paper.Point, m: Mods): void {
    if (!this.start) return;
    this.preview?.remove();
    const end = m.alt ? p : this.e.snap(p);
    this.preview = this.build(this.start, end, m);
    this.uiStroke(this.preview);
    this.preview.fillColor = this.kind === "line" ? null : new paper.Color(79 / 255, 70 / 255, 229 / 255, 0.08);
    this.e.addUi(this.preview, "shape");
    this.e.hintValue(this.describe(this.start, end, m));
  }

  up(p: paper.Point, m: Mods): void {
    const start = this.start;
    this.start = null;
    this.preview?.remove();
    this.preview = null;
    this.e.clearUi("shape");
    this.e.clearUi("snap");
    this.e.hintValue("");
    if (!start) return;
    const end = m.alt ? p : this.e.snap(p);
    if (end.getDistance(start) < Math.max(0.5, this.e.px(3))) return;
    const path = this.build(start, end, m);
    path.data = {};
    if (path.bounds.width < 0.3 && path.bounds.height < 0.3) {
      path.remove();
      return;
    }
    this.e.addItem(path, { select: true });
    this.e.commit();
  }

  cancel(): void {
    this.start = null;
    this.preview?.remove();
    this.preview = null;
    this.e.clearUi("shape");
  }

  key(key: string): boolean {
    if (key === "Escape" && this.start) {
      this.cancel();
      return true;
    }
    return false;
  }

  private rectFor(a: paper.Point, b: paper.Point, m: Mods): paper.Rectangle {
    let dx = b.x - a.x;
    let dy = b.y - a.y;
    if (m.shift) {
      const s = Math.max(Math.abs(dx), Math.abs(dy));
      dx = Math.sign(dx || 1) * s;
      dy = Math.sign(dy || 1) * s;
    }
    if (m.alt) return new paper.Rectangle(new paper.Point(a.x - dx, a.y - dy), new paper.Point(a.x + dx, a.y + dy));
    return new paper.Rectangle(a, new paper.Point(a.x + dx, a.y + dy));
  }

  private build(a: paper.Point, b: paper.Point, m: Mods): paper.Path {
    switch (this.kind) {
      case "rect": {
        const rect = this.rectFor(a, b, m);
        const radius = Math.min(this.e.cornerRadius, rect.width / 2, rect.height / 2);
        return new paper.Path.Rectangle({ rectangle: rect, radius: radius > 0 ? radius : undefined, insert: false });
      }
      case "ellipse":
        return new paper.Path.Ellipse({ rectangle: this.rectFor(a, b, m), insert: false });
      case "line": {
        let end = b;
        if (m.shift) {
          const v = b.subtract(a);
          end = a.add(new paper.Point({ length: v.length, angle: Math.round(v.angle / 15) * 15 }));
        }
        return new paper.Path.Line({ from: a, to: end, insert: false });
      }
      case "polygon": {
        const v = b.subtract(a);
        const poly = new paper.Path.RegularPolygon({ center: a, sides: this.e.polygonSides, radius: Math.max(v.length, 0.01), insert: false });
        // RegularPolygon puts its first vertex at the top; rotate it toward the cursor
        poly.rotate(v.angle + 90, a);
        return poly;
      }
    }
  }

  private describe(a: paper.Point, b: paper.Point, m: Mods): string {
    if (this.kind === "line") return `${(Math.round(b.subtract(a).length * 100) / 100).toString()} mm`;
    if (this.kind === "polygon") return `R ${(Math.round(b.subtract(a).length * 100) / 100).toString()} mm`;
    const r = this.rectFor(a, b, m);
    return `${Math.round(Math.abs(r.width) * 100) / 100} × ${Math.round(Math.abs(r.height) * 100) / 100} mm`;
  }
}

// ---------------------------------------------------------------------------
// Dimension (annotation) tool
// ---------------------------------------------------------------------------

class DimensionTool extends BaseTool {
  cursor = "crosshair";
  hint = "hint.dimension";
  private a: paper.Point | null = null;
  private preview: paper.Path | null = null;

  down(p: paper.Point, m: Mods): void {
    const pt = this.e.snap(p, [], { from: this.a ?? undefined, constrain: m.shift });
    if (!this.a) {
      this.a = pt;
      return;
    }
    if (pt.getDistance(this.a) < 0.3) return;
    const group = this.e.createDimension(this.a, pt);
    this.cancel();
    this.e.selectItems([group]);
    this.e.commit();
  }

  move(p: paper.Point, m: Mods): void {
    if (!this.a) {
      this.e.snap(p); // show what the first click would lock onto
      return;
    }
    this.preview?.remove();
    this.preview = new paper.Path.Line({ from: this.a, to: this.e.snap(p, [], { from: this.a, constrain: m.shift }), insert: false });
    this.uiStroke(this.preview, true);
    this.e.addUi(this.preview, "dimpreview");
  }

  key(key: string): boolean {
    if (key === "Escape" && this.a) {
      this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.a = null;
    this.preview?.remove();
    this.preview = null;
    this.e.clearUi("dimpreview");
    this.e.clearUi("snap");
  }
}

// ---------------------------------------------------------------------------
// Measure: distance / ΔX / ΔY / angle between two snapped points
// ---------------------------------------------------------------------------

class MeasureTool extends BaseTool {
  cursor = "crosshair";
  hint = "hint.measure";
  private a: paper.Point | null = null;
  private b: paper.Point | null = null;
  /** true once the second point is placed: the reading stays on screen until the next click */
  private fixed = false;

  down(p: paper.Point, m: Mods): void {
    if (!this.a || this.fixed) {
      this.a = this.e.snap(p);
      this.b = null;
      this.fixed = false;
      this.e.setMeasurement(null, null);
      this.draw();
      return;
    }
    const b = this.e.snap(p, [], { from: this.a, constrain: m.shift });
    if (b.getDistance(this.a) < 1e-9) return;
    this.b = b;
    this.fixed = true;
    this.e.setMeasurement(this.a, this.b);
    this.draw();
  }

  move(p: paper.Point, m: Mods): void {
    if (!this.a || this.fixed) {
      this.e.snap(p); // preview what a click would lock onto
      return;
    }
    this.b = this.e.snap(p, [], { from: this.a, constrain: m.shift });
    this.e.setMeasurement(this.a, this.b);
    this.draw();
  }

  key(key: string): boolean {
    if (key === "Enter" && this.fixed) {
      if (this.e.measurementToDimension()) this.cancel();
      return true;
    }
    if (key === "Escape" && this.a) {
      this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.a = null;
    this.b = null;
    this.fixed = false;
    this.e.clearUi("measure");
    this.e.clearUi("snap");
    this.e.setMeasurement(null, null);
    this.e.hintValue("");
  }

  drawOverlay(): void {
    this.draw();
  }

  private draw(): void {
    const e = this.e;
    e.clearUi("measure");
    if (!this.a) return;
    const tick = (pt: paper.Point) => {
      const c = new paper.Path.Circle({ center: pt, radius: e.px(3), insert: false });
      c.fillColor = new paper.Color("#0ea5e9");
      e.addUi(c, "measure");
    };
    tick(this.a);
    const m = e.measurement;
    if (!this.b || !m) return;
    tick(this.b);
    const line = new paper.Path.Line({ from: this.a, to: this.b, insert: false });
    line.strokeColor = new paper.Color("#0ea5e9");
    line.strokeWidth = 1.5;
    line.strokeScaling = false;
    line.dashArray = this.fixed ? [] : [5, 3];
    e.addUi(line, "measure");
    const text = `${formatMm(m.distance)} mm · ${m.angle}°`;
    const label = e.screenText(this.a.add(this.b).divide(2).add([0, -e.px(8)]), text, 12, "#0369a1", "center");
    // white backing so the reading stays legible over shapes, guides and a busy photo
    const backing = new paper.Path.Rectangle({ rectangle: label.bounds.expand(e.px(6), e.px(3)), radius: e.px(3), insert: false });
    backing.fillColor = new paper.Color(1, 1, 1, 0.9);
    e.addUi(backing, "measure");
    e.addUi(label, "measure");
    e.hintValue(`${text} · ΔX ${formatMm(m.dx)} · ΔY ${formatMm(m.dy)}`);
  }
}

// ---------------------------------------------------------------------------
// Calibrate the reference image: two clicks on a known distance
// ---------------------------------------------------------------------------

class CalibrateTool extends BaseTool {
  cursor = "crosshair";
  hint = "hint.calibrate";
  private a: paper.Point | null = null;

  // Raw points on purpose: snapping to the grid or to drawn nodes would move the click away from
  // the feature on the photo and falsify the scale. Zoom in to click precisely instead.
  down(p: paper.Point): void {
    if (!this.e.background) {
      this.e.hint("hint.noBackground");
      return;
    }
    if (!this.a) {
      this.a = p.clone();
      this.draw(p);
      return;
    }
    if (p.getDistance(this.a) < this.e.px(4)) return;
    const a = this.a;
    this.a = null;
    this.draw(p, a);
    this.e.emit("calibrate", [a.x, a.y], [p.x, p.y]);
  }

  move(p: paper.Point): void {
    if (this.a) this.draw(p, this.a);
  }

  key(key: string): boolean {
    if (key === "Escape" && this.a) {
      this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.a = null;
    this.e.clearUi("calib");
    this.e.hintValue("");
  }

  private draw(p: paper.Point, from?: paper.Point): void {
    const e = this.e;
    e.clearUi("calib");
    const cross = (pt: paper.Point) => {
      const r = e.px(8);
      for (const [dx, dy] of [[r, 0], [0, r]]) {
        const l = new paper.Path.Line({ from: pt.subtract([dx, dy]), to: pt.add([dx, dy]), insert: false });
        l.strokeColor = new paper.Color("#e11d48");
        l.strokeWidth = 1.5;
        l.strokeScaling = false;
        e.addUi(l, "calib");
      }
    };
    cross(p);
    if (!from) return;
    cross(from);
    const line = new paper.Path.Line({ from, to: p, insert: false });
    line.strokeColor = new paper.Color("#e11d48");
    line.strokeWidth = 1;
    line.strokeScaling = false;
    line.dashArray = [5, 3];
    e.addUi(line, "calib");
    e.hintValue(`${formatMm(p.getDistance(from))} mm (${e.background?.calibrated ? "✓" : "?"})`);
  }
}


// ---------------------------------------------------------------------------
// Perspective: the four corners of a known rectangle on the reference photo
// ---------------------------------------------------------------------------

class PerspectiveTool extends BaseTool {
  cursor = "crosshair";
  hint = "hint.perspective";
  private points: paper.Point[] = [];

  // raw points, like the calibration tool: snapping would move the click off the photo's corner
  down(p: paper.Point): void {
    if (!this.e.background) {
      this.e.hint("hint.noBackground");
      return;
    }
    if (this.points.some((q) => q.getDistance(p) < this.e.px(4))) return;
    this.points.push(p.clone());
    this.draw();
    if (this.points.length === 4) {
      const pts = this.points.map((q) => [q.x, q.y] as [number, number]);
      this.points = [];
      this.e.hintValue("");
      this.e.emit("perspective", pts);
    }
  }

  move(p: paper.Point): void {
    if (this.points.length) this.draw(p);
  }

  key(key: string): boolean {
    if (key === "Escape" && this.points.length) {
      this.cancel();
      return true;
    }
    if (key === "Backspace" && this.points.length) {
      this.points.pop();
      this.draw();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.points = [];
    this.e.clearUi("persp");
    this.e.hintValue("");
  }

  private draw(hover?: paper.Point): void {
    const e = this.e;
    e.clearUi("persp");
    const pts = hover && this.points.length < 4 ? [...this.points, hover] : this.points;
    if (pts.length > 1) {
      const outline = new paper.Path({ segments: pts, closed: pts.length === 4, insert: false });
      outline.strokeColor = new paper.Color("#e11d48");
      outline.strokeWidth = 1;
      outline.strokeScaling = false;
      outline.dashArray = [5, 3];
      e.addUi(outline, "persp");
    }
    this.points.forEach((pt, i) => {
      const dot = new paper.Path.Circle({ center: pt, radius: e.px(4), insert: false });
      dot.strokeColor = new paper.Color("#e11d48");
      dot.strokeWidth = 1.5;
      dot.strokeScaling = false;
      e.addUi(dot, "persp");
      e.addUi(e.screenText(pt.add([e.px(7), -e.px(7)]), String(i + 1), 12, "#e11d48"), "persp");
    });
    e.hintValue(`${this.points.length} / 4`);
  }
}


// ---------------------------------------------------------------------------
// Arc through 3 points: start, end, then a point on the arc
// ---------------------------------------------------------------------------

class ArcTool extends BaseTool {
  cursor = "crosshair";
  hint = "hint.arc";
  private start: paper.Point | null = null;
  private end: paper.Point | null = null;

  down(p: paper.Point, m: Mods): void {
    if (!this.start) {
      if (!this.activeLayerUsable()) return;
      this.start = this.e.snap(p);
      return;
    }
    if (!this.end) {
      const end = this.e.snap(p, [], { from: this.start, constrain: m.shift });
      if (end.getDistance(this.start) < 1e-6) return;
      this.end = end;
      this.e.hint("hint.arcThrough");
      return;
    }
    const through = this.e.snap(p);
    const nodes = arcThrough([this.start.x, this.start.y], [through.x, through.y], [this.end.x, this.end.y]);
    this.cancel();
    this.e.addContours([nodes], { closed: false });
    this.e.hint(this.hint);
  }

  move(p: paper.Point, m: Mods): void {
    this.e.clearUi("arc");
    if (!this.start) {
      this.e.snap(p);
      return;
    }
    let preview: paper.Path;
    if (!this.end) {
      preview = new paper.Path.Line({ from: this.start, to: this.e.snap(p, [], { from: this.start, constrain: m.shift }), insert: false });
    } else {
      const through = this.e.snap(p);
      const nodes = arcThrough([this.start.x, this.start.y], [through.x, through.y], [this.end.x, this.end.y]);
      preview = this.e.contourToPath(nodes, false);
      const circle = circleThrough([this.start.x, this.start.y], [through.x, through.y], [this.end.x, this.end.y]);
      this.e.hintValue(circle ? `R ${formatMm(circle.r)} mm` : "");
    }
    this.uiStroke(preview, true);
    this.e.addUi(preview, "arc");
  }

  key(key: string): boolean {
    if (key === "Escape" && this.start) {
      this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.start = null;
    this.end = null;
    this.e.clearUi("arc");
    this.e.clearUi("snap");
    this.e.hintValue("");
  }
}

class PanTool extends BaseTool {
  cursor = "grab";
  hint = "hint.pan";
}

export function createTool(name: ToolName, engine: EditorEngine): ToolHandler {
  switch (name) {
    case "select":
      return new SelectTool(engine);
    case "node":
      return new NodeTool(engine);
    case "pen":
      return new PenTool(engine);
    case "rect":
    case "ellipse":
    case "line":
    case "polygon":
      return new ShapeTool(engine, name);
    case "dimension":
      return new DimensionTool(engine);
    case "measure":
      return new MeasureTool(engine);
    case "arc":
      return new ArcTool(engine);
    case "calibrate":
      return new CalibrateTool(engine);
    case "perspective":
      return new PerspectiveTool(engine);
    case "pan":
      return new PanTool(engine);
  }
}
