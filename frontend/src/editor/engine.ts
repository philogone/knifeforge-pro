import paper from "paper";

import { calibrate, MAX_IMAGE_PX, type BackgroundState, type Straighten } from "./background";
import type { ShapePart } from "./shapes";
import { docToPixel, planRectify, rectangleTargets, rectifiedPlacement, rectifyImage, type RectifyPlan } from "./perspective";
import { chamferCorner, circleNodes, filletCorner, holeCentres, type Axis, type CornerError, type HolePattern } from "./drafting";
import { MAX_GRID_MM, MAX_ZOOM, MIN_GRID_MM, MIN_ZOOM, PX_PER_MM_CSS, ROLE_STYLE, UI_COLOR, defaultLayers } from "./constants";
import { History } from "./history";
import { createTool, type ToolHandler } from "./tools";
import type {
  Bounds,
  DesignDocument,
  DimensionObject,
  DocLayer,
  DocNode,
  DocObject,
  Guide,
  LayerRole,
  PathObject,
  SelectionInfo,
  ToolName,
} from "./types";
import type { ViewTransform } from "./view";

export interface Mods {
  shift: boolean;
  alt: boolean;
  ctrl: boolean;
}

export interface EngineEvents {
  change: [];
  selection: [SelectionInfo];
  view: [];
  cursor: [number, number];
  tool: [ToolName];
  layers: [];
  hint: [string];
  value: [string];
  /** the reference image changed (placement, opacity, loaded…) */
  background: [];
  /** the calibration tool picked two points on the reference image */
  calibrate: [[number, number], [number, number]];
  /** the perspective tool picked the four corners of a rectangle on the reference image */
  perspective: [[number, number][]];
  /** the measure tool's current reading (null when cleared) */
  measure: [Measurement | null];
  /** guides changed (added, moved, removed, or restored by undo) */
  guides: [];
  /** a click-by-click tool (pen) started or finished a path: numeric entry is possible meanwhile */
  drawing: [boolean];
}

export interface CornerReport {
  done: number;
  /** corners left as they were, by reason */
  skipped: Partial<Record<CornerError | "curvedEdge", number>>;
}

export interface Measurement {
  a: [number, number];
  b: [number, number];
  distance: number;
  dx: number;
  dy: number;
  /** degrees, counter-clockwise from +x as a draughtsman reads it (y is flipped) */
  angle: number;
}

export type SnapKind = "node" | "intersection" | "midpoint" | "center" | "path" | "guide" | "grid" | "angle";

export interface SnapOptions {
  nodes: boolean;
  intersections: boolean;
  midpoints: boolean;
  centers: boolean;
  /** nearest point on any outline */
  path: boolean;
  guides: boolean;
  grid: boolean;
}

export interface SnapRequest {
  /** start point of the segment being drawn: enables the angle constraint */
  from?: paper.Point;
  /** lock the direction from `from` to multiples of 15° (Shift) */
  constrain?: boolean;
  /** paths whose curves must not attract (the path whose node is being dragged) */
  skipPaths?: paper.Path[];
  /** nodes that must not attract (the node being dragged) */
  skipSegments?: paper.Segment[];
}

interface SnapHit {
  kind: SnapKind;
  point: paper.Point;
}

type Listener<T extends unknown[]> = (...args: T) => void;
export type EditableItem = paper.Path | paper.CompoundPath;
export type BooleanOp = "unite" | "subtract" | "intersect" | "exclude";
export type AlignKind = "left" | "centerH" | "right" | "top" | "middleV" | "bottom";

const DIM_TEXT_MM = 3.5;
const DIM_ARROW_MM = 2.4;
const round4 = (v: number) => Math.round(v * 10000) / 10000;
let idCounter = 0;

export function newId(prefix = "o"): string {
  idCounter += 1;
  return `${prefix}${Date.now().toString(36)}${idCounter.toString(36)}${Math.floor(Math.random() * 1296).toString(36)}`;
}

export class EditorEngine {
  readonly scope: paper.PaperScope;
  readonly canvas: HTMLCanvasElement;
  readonly ui: paper.Layer;
  /** reference image layer: always at the bottom, locked, never part of the document */
  private readonly bgLayer: paper.Layer;
  private bg: BackgroundState | null = null;
  private raster: paper.Raster | null = null;
  private lastMeasure: Measurement | null = null;
  layers: DocLayer[] = defaultLayers();
  activeLayerId = "cut";

  gridSize = 1;
  snapOptions: SnapOptions = { nodes: true, intersections: true, midpoints: true, centers: true, path: false, guides: true, grid: true };
  /** attraction distance, in screen pixels (so it feels the same at any zoom) */
  snapRadiusPx = 10;
  /** labels shown next to the snap marker, set by the UI in its language */
  snapLabels: Partial<Record<SnapKind, string>> = {};
  /** what the last snap() call locked onto (null = free point) */
  lastSnap: SnapHit | null = null;
  guides: Guide[] = [];
  /** guide being dragged out of a ruler (drawn, not yet part of the document) */
  previewGuide: Guide | null = null;
  /** mirror axis used by the pen: a half outline is completed by its mirror image */
  symmetry: Axis | null = null;

  get snapToGrid(): boolean {
    return this.snapOptions.grid;
  }
  set snapToGrid(on: boolean) {
    this.snapOptions.grid = on;
  }
  get snapToNodes(): boolean {
    return this.snapOptions.nodes;
  }
  set snapToNodes(on: boolean) {
    this.snapOptions.nodes = on;
  }
  /** Corner radius (mm) applied by the rectangle tool */
  cornerRadius = 0;
  /** Number of sides used by the polygon tool */
  polygonSides = 6;

  private paperLayers = new Map<string, paper.Layer>();
  private listeners: { [K in keyof EngineEvents]?: Listener<EngineEvents[K]>[] } = {};
  private history = new History();
  private savedState = "";
  private toolName: ToolName = "select";
  private handler: ToolHandler;
  private paperTool: paper.Tool;
  private selected: paper.Item[] = [];
  private spaceDown = false;
  private panning: { startX: number; startY: number; center: paper.Point } | null = null;
  private clipboard: DocObject[] = [];
  private cursorWorld: [number, number] = [0, 0];

  // node-tool state
  nodeTargets: paper.Path[] = [];
  selectedSegments: paper.Segment[] = [];

  constructor(canvas: HTMLCanvasElement, options: { headless?: boolean } = {}) {
    this.canvas = canvas;
    this.scope = new paper.PaperScope();
    this.scope.setup(canvas);
    if (options.headless) this.scope.view.autoUpdate = false;
    this.bgLayer = new paper.Layer({ name: "__background" });
    this.bgLayer.locked = true;
    this.ui = new paper.Layer({ name: "__ui" });
    this.rebuildLayers();
    this.handler = createTool("select", this);

    this.paperTool = new paper.Tool();
    this.paperTool.onMouseDown = (e: paper.ToolEvent) => this.onMouseDown(e);
    this.paperTool.onMouseDrag = (e: paper.ToolEvent) => this.onMouseDrag(e);
    this.paperTool.onMouseUp = (e: paper.ToolEvent) => this.onMouseUp(e);
    this.paperTool.onMouseMove = (e: paper.ToolEvent) => this.onMouseMove(e);
    this.paperTool.activate();

    canvas.addEventListener("wheel", this.onWheel, { passive: false });
    canvas.addEventListener("dblclick", this.onDblClick);
    this.view.center = new paper.Point(100, 60);
    this.view.zoom = 4;
    const state = JSON.stringify(this.exportDocument());
    this.history.reset(state);
    this.savedState = state;
  }

  destroy(): void {
    this.canvas.removeEventListener("wheel", this.onWheel);
    this.canvas.removeEventListener("dblclick", this.onDblClick);
    this.scope.project.remove();
    this.listeners = {};
  }

  // ------------------------------------------------------------------ events
  on<K extends keyof EngineEvents>(name: K, fn: Listener<EngineEvents[K]>): () => void {
    const list = (this.listeners[name] ??= []) as Listener<EngineEvents[K]>[];
    list.push(fn);
    return () => {
      const i = list.indexOf(fn);
      if (i >= 0) list.splice(i, 1);
    };
  }

  emit<K extends keyof EngineEvents>(name: K, ...args: EngineEvents[K]): void {
    for (const fn of (this.listeners[name] ?? []) as Listener<EngineEvents[K]>[]) fn(...args);
  }

  hint(key: string): void {
    this.emit("hint", key);
  }

  // -------------------------------------------------------------------- view
  get view(): paper.View {
    return this.scope.view;
  }

  get zoom(): number {
    return this.view.zoom;
  }

  get viewTransform(): ViewTransform {
    return {
      centerX: this.view.center.x,
      centerY: this.view.center.y,
      zoom: this.view.zoom,
      width: this.view.viewSize.width,
      height: this.view.viewSize.height,
    };
  }

  resize(width: number, height: number): void {
    this.view.viewSize = new paper.Size(Math.max(1, width), Math.max(1, height));
    this.refreshOverlay();
    this.emit("view");
  }

  setZoom(zoom: number, anchor?: paper.Point): void {
    const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
    if (anchor) {
      // keep the world point under `anchor` (project coords) fixed on screen
      const before = this.view.projectToView(anchor);
      this.view.zoom = next;
      const after = this.view.projectToView(anchor);
      this.view.center = this.view.center.add(after.subtract(before).divide(next));
    } else {
      this.view.zoom = next;
    }
    this.refreshOverlay();
    this.emit("view");
  }

  zoomActual(): void {
    this.setZoom(PX_PER_MM_CSS);
  }

  panByScreen(dx: number, dy: number): void {
    this.view.center = this.view.center.subtract(new paper.Point(dx, dy).divide(this.view.zoom));
    this.emit("view");
  }

  zoomToFit(padding = 48): void {
    const items = this.docItems().filter((i) => i.visible);
    let bounds: paper.Rectangle | null = null;
    for (const item of items) bounds = bounds ? bounds.unite(item.bounds) : item.bounds.clone();
    if (!bounds || bounds.width < 1e-6 || bounds.height < 1e-6) bounds = new paper.Rectangle(0, 0, 200, 120);
    const size = this.view.viewSize;
    const zoom = Math.min((size.width - padding * 2) / bounds.width, (size.height - padding * 2) / bounds.height);
    this.view.center = bounds.center;
    this.setZoom(Math.min(zoom, 60));
  }

  private onWheel = (e: WheelEvent): void => {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    const anchor = this.view.viewToProject(new paper.Point(e.clientX - rect.left, e.clientY - rect.top));
    if (e.ctrlKey || e.metaKey || !e.shiftKey) {
      const factor = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015));
      this.setZoom(this.view.zoom * factor, anchor);
    } else {
      this.panByScreen(-e.deltaY, 0);
    }
  };

  // ---------------------------------------------------------------- tools
  get tool(): ToolName {
    return this.toolName;
  }

  /** The active tool's event handler (exposed for tests and keyboard routing). */
  get activeHandler(): ToolHandler {
    return this.handler;
  }

  setTool(name: ToolName): void {
    if (name === this.toolName) return;
    this.handler.cancel();
    this.toolName = name;
    this.handler = createTool(name, this);
    this.nodeTargets = name === "node" ? this.selected.filter((i): i is paper.Path => i instanceof paper.Path) : [];
    if (name === "node" && this.nodeTargets.length === 0) this.nodeTargets = this.pathsOf(this.selected);
    this.selectedSegments = [];
    this.canvas.style.cursor = this.handler.cursor;
    this.refreshOverlay();
    this.emit("tool", name);
    this.emitSelection();
    this.hint(this.handler.hint);
  }

  setSpace(down: boolean): void {
    this.spaceDown = down;
    this.canvas.style.cursor = down ? "grab" : this.handler.cursor;
  }

  private mods(e: paper.ToolEvent): Mods {
    return { shift: e.modifiers.shift, alt: e.modifiers.alt, ctrl: e.modifiers.control || e.modifiers.command };
  }

  private nativeEvent(e: paper.ToolEvent): MouseEvent | null {
    const n = (e as unknown as { event?: Event }).event;
    return n && "button" in n ? (n as MouseEvent) : null;
  }

  private onMouseDown(e: paper.ToolEvent): void {
    const native = this.nativeEvent(e);
    if (native && (native.button === 1 || this.spaceDown || this.toolName === "pan")) {
      this.panning = { startX: native.clientX, startY: native.clientY, center: this.view.center.clone() };
      this.canvas.style.cursor = "grabbing";
      return;
    }
    if (native && native.button === 2) return;
    this.handler.down(e.point, this.mods(e));
  }

  private onMouseDrag(e: paper.ToolEvent): void {
    const native = this.nativeEvent(e);
    if (this.panning && native) {
      const dx = native.clientX - this.panning.startX;
      const dy = native.clientY - this.panning.startY;
      this.view.center = this.panning.center.subtract(new paper.Point(dx, dy).divide(this.view.zoom));
      this.emit("view");
      return;
    }
    this.setCursorWorld(e.point);
    this.handler.drag(e.point, this.mods(e));
  }

  private onMouseUp(e: paper.ToolEvent): void {
    if (this.panning) {
      this.panning = null;
      this.canvas.style.cursor = this.spaceDown ? "grab" : this.handler.cursor;
      return;
    }
    this.handler.up(e.point, this.mods(e));
  }

  private onMouseMove(e: paper.ToolEvent): void {
    this.setCursorWorld(e.point);
    this.handler.move(e.point, this.mods(e));
  }

  private onDblClick = (e: MouseEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    const p = this.view.viewToProject(new paper.Point(e.clientX - rect.left, e.clientY - rect.top));
    this.handler.doubleClick(p, { shift: e.shiftKey, alt: e.altKey, ctrl: e.ctrlKey || e.metaKey });
  };

  private setCursorWorld(p: paper.Point): void {
    this.cursorWorld = [p.x, p.y];
    this.emit("cursor", p.x, p.y);
  }

  get cursor(): [number, number] {
    return this.cursorWorld;
  }

  /** Forward a key to the active tool. Returns true if the tool consumed it. */
  toolKey(key: string): boolean {
    return this.handler.key(key);
  }

  // -------------------------------------------------------------- snapping
  /** Closest path node within `radius` (world mm), ignoring `exclude` items and hidden/locked layers. */
  nearestNode(point: paper.Point, radius: number, exclude: paper.Item[] = [], skipSegments: paper.Segment[] = []): paper.Point | null {
    if (!this.snapOptions.nodes) return null;
    let best: paper.Point | null = null;
    let bestDist = radius;
    for (const path of this.snapPaths(point, radius, exclude)) {
      for (const seg of path.segments) {
        if (skipSegments.includes(seg)) continue;
        const d = seg.point.getDistance(point);
        if (d < bestDist) {
          bestDist = d;
          best = seg.point;
        }
      }
    }
    return best ? best.clone() : null;
  }

  /** Paths of visible, unlocked document items whose bounds come within `radius` of `point`. */
  private snapPaths(point: paper.Point, radius: number, exclude: paper.Item[]): paper.Path[] {
    const items = this.docItems().filter(
      (i) =>
        i.visible &&
        i.parent?.visible !== false &&
        !i.parent?.locked &&
        !exclude.includes(i) &&
        i.data?.kind !== "dim" &&
        i.bounds.expand(radius * 2).contains(point),
    );
    return this.pathsOf(items);
  }

  /**
   * Snap a point, by priority: exact geometric points (node, intersection, midpoint, centre),
   * then a point on an outline, then guides and the grid (each axis on its own). With `from` +
   * `constrain` (Shift) the direction is locked to 15° steps instead, and the length to the grid.
   */
  snap(point: paper.Point, exclude: paper.Item[] = [], req: SnapRequest = {}): paper.Point {
    this.clearUi("snap");
    this.lastSnap = null;
    if (req.from && req.constrain) return this.snapAngle(point, req.from);

    const hit = this.findSnap(point, this.px(this.snapRadiusPx), exclude, req);
    if (hit) {
      this.lastSnap = hit;
      this.showSnapMarker(hit.point, hit.kind);
      return hit.point.clone();
    }
    return this.snapToGuidesAndGrid(point);
  }

  private findSnap(point: paper.Point, r: number, exclude: paper.Item[], req: SnapRequest): SnapHit | null {
    const o = this.snapOptions;
    const skipPaths = req.skipPaths ?? [];
    const own = this.snapPaths(point, r, exclude).filter((p) => !skipPaths.includes(p));
    const closest = (kind: SnapKind, candidates: paper.Point[]): SnapHit | null => {
      let best: paper.Point | null = null;
      let bestDist = r;
      for (const c of candidates) {
        const d = c.getDistance(point);
        if (d < bestDist) {
          bestDist = d;
          best = c;
        }
      }
      return best ? { kind, point: best.clone() } : null;
    };

    if (o.nodes) {
      const node = this.nearestNode(point, r, exclude, req.skipSegments ?? []);
      if (node) return { kind: "node", point: node };
    }
    if (o.intersections && own.length > 1) {
      const pts: paper.Point[] = [];
      const near = own.slice(0, 40); // bounded cost: only paths around the cursor, at most 40
      for (let i = 0; i < near.length; i++) {
        for (let j = i + 1; j < near.length; j++) {
          if (!near[i].bounds.intersects(near[j].bounds)) continue;
          for (const loc of near[i].getIntersections(near[j])) pts.push(loc.point);
        }
      }
      const hit = closest("intersection", pts);
      if (hit) return hit;
    }
    if (o.midpoints) {
      const mids = own.flatMap((p) => p.curves.filter((c) => c.length > 1e-6).map((c) => c.getPointAt(c.length / 2)));
      const hit = closest("midpoint", mids);
      if (hit) return hit;
    }
    if (o.centers) {
      const hit = closest("center", own.filter((p) => p.closed).map((p) => p.bounds.center));
      if (hit) return hit;
    }
    if (o.path) {
      const hit = closest("path", own.map((p) => p.getNearestPoint(point)));
      if (hit) return hit;
    }
    return null;
  }

  /** Guides first (each axis on its own), then the grid for any axis no guide claimed. */
  private snapToGuidesAndGrid(point: paper.Point): paper.Point {
    let x = point.x;
    let y = point.y;
    let onGuideX = false;
    let onGuideY = false;
    if (this.snapOptions.guides && this.guides.length) {
      let bestX = this.px(this.snapRadiusPx);
      let bestY = bestX;
      for (const g of this.guides) {
        const d = Math.abs((g.axis === "x" ? point.x : point.y) - g.pos);
        if (g.axis === "x" && d < bestX) {
          bestX = d;
          x = g.pos;
          onGuideX = true;
        } else if (g.axis === "y" && d < bestY) {
          bestY = d;
          y = g.pos;
          onGuideY = true;
        }
      }
    }
    if (this.snapOptions.grid) {
      if (!onGuideX) x = this.snapAxis(point.x);
      if (!onGuideY) y = this.snapAxis(point.y);
    }
    const out = new paper.Point(x, y);
    if (onGuideX || onGuideY) {
      this.lastSnap = { kind: "guide", point: out };
      this.showSnapMarker(out, "guide");
    }
    return out;
  }

  /** Lock the direction from `from` to the nearest 15°, and the length to the grid step. */
  private snapAngle(point: paper.Point, from: paper.Point): paper.Point {
    const v = point.subtract(from);
    const angle = Math.round(v.angle / 15) * 15;
    const length = this.snapOptions.grid ? Math.round(v.length / this.gridSize) * this.gridSize : v.length;
    const rad = (angle * Math.PI) / 180;
    const out = new paper.Point(round4(from.x + length * Math.cos(rad)), round4(from.y + length * Math.sin(rad)));
    this.lastSnap = { kind: "angle", point: out };
    this.showSnapMarker(out, "angle", `${normalizeAngle(-angle)}°`);
    return out;
  }

  showSnapMarker(p: paper.Point, kind: SnapKind = "node", text?: string): void {
    this.clearUi("snap");
    const r = this.px(5);
    let marker: paper.Item;
    if (kind === "midpoint") {
      marker = new paper.Path.RegularPolygon({ center: p, sides: 3, radius: r * 1.3, insert: false });
    } else if (kind === "center" || kind === "angle") {
      marker = new paper.CompoundPath({
        children: [
          new paper.Path.Line({ from: p.add([-r, 0]), to: p.add([r, 0]), insert: false }),
          new paper.Path.Line({ from: p.add([0, -r]), to: p.add([0, r]), insert: false }),
        ],
        insert: false,
      });
    } else if (kind === "intersection") {
      marker = new paper.CompoundPath({
        children: [
          new paper.Path.Line({ from: p.add([-r, -r]), to: p.add([r, r]), insert: false }),
          new paper.Path.Line({ from: p.add([r, -r]), to: p.add([-r, r]), insert: false }),
        ],
        insert: false,
      });
    } else if (kind === "path" || kind === "guide") {
      marker = new paper.Path.Rectangle({ center: p, size: [r * 1.4, r * 1.4], insert: false });
      marker.rotate(45);
    } else {
      marker = new paper.Path.Circle({ center: p, radius: r, insert: false });
    }
    marker.strokeColor = new paper.Color("#f59e0b");
    marker.strokeWidth = 2;
    marker.strokeScaling = false;
    marker.fillColor = null;
    this.addUi(marker, "snap");
    const label = text ?? this.snapLabels[kind];
    if (label) this.addUi(this.screenText(p.add([this.px(9), -this.px(8)]), label, 11, "#b45309"), "snap");
  }

  /**
   * Overlay text that is `sizePx` tall on screen at any zoom. Built at its real pixel size and
   * scaled down by the zoom: a 1.3-unit font scaled up by the view (the naive way) is laid out by
   * the canvas at that tiny size, and its glyph positions come out garbled.
   */
  screenText(at: paper.Point, content: string, sizePx: number, color: string, justification: "left" | "center" = "left"): paper.PointText {
    const t = new paper.PointText({ point: at, content, insert: false });
    t.fontSize = sizePx;
    t.fontFamily = '"IBM Plex Sans", sans-serif';
    t.justification = justification;
    t.fillColor = new paper.Color(color);
    t.scale(1 / this.view.zoom, at);
    return t;
  }

  /** Live readout (size, length…) shown in the status bar while drawing. */
  hintValue(text: string): void {
    this.emit("value", text);
  }

  // ----------------------------------------------------------- UI overlay
  clearUi(tag?: string): void {
    for (const child of [...this.ui.children]) {
      if (!tag || child.data?.ui === tag) child.remove();
    }
  }

  addUi(item: paper.Item, tag: string): void {
    item.data = { ...(item.data ?? {}), ui: tag };
    this.ui.addChild(item);
  }

  /** px → world units at the current zoom */
  px(n: number): number {
    return n / this.view.zoom;
  }

  refreshOverlay(): void {
    this.clearUi("sel");
    this.clearUi("nodes");
    this.handler.drawOverlay();
  }

  // --------------------------------------------------------------- layers
  private rebuildLayers(): void {
    for (const layer of this.paperLayers.values()) layer.remove();
    this.paperLayers.clear();
    for (const meta of this.layers) this.ensurePaperLayer(meta);
    this.project.addLayer(this.ui);
  }

  get project(): paper.Project {
    return this.scope.project;
  }

  private ensurePaperLayer(meta: DocLayer): paper.Layer {
    let layer = this.paperLayers.get(meta.id);
    if (!layer) {
      layer = new paper.Layer({ name: meta.id });
      layer.data = { layerId: meta.id };
      this.paperLayers.set(meta.id, layer);
    }
    layer.visible = meta.visible;
    layer.locked = meta.locked;
    return layer;
  }

  private syncLayerOrder(): void {
    for (const meta of this.layers) {
      const layer = this.paperLayers.get(meta.id);
      if (layer) this.project.addLayer(layer);
    }
    this.project.addLayer(this.ui);
  }

  layerMeta(id: string): DocLayer | undefined {
    return this.layers.find((l) => l.id === id);
  }

  addLayer(name: string, role: LayerRole): DocLayer {
    const meta = this.createLayer(name, role);
    this.activeLayerId = meta.id;
    this.emit("layers");
    this.commit();
    return meta;
  }

  /** New layer, without making it active nor committing (the caller does). */
  private createLayer(name: string, role: LayerRole): DocLayer {
    const meta: DocLayer = { id: newId("l"), name: name.slice(0, 100) || "Layer", role, visible: true, locked: false };
    this.layers.push(meta);
    this.ensurePaperLayer(meta);
    this.syncLayerOrder();
    this.emit("layers");
    return meta;
  }

  updateLayer(id: string, patch: Partial<Pick<DocLayer, "name" | "role" | "visible" | "locked">>): void {
    const meta = this.layerMeta(id);
    if (!meta) return;
    Object.assign(meta, patch);
    const layer = this.ensurePaperLayer(meta);
    if (patch.role) for (const item of [...layer.children]) this.styleItem(item as paper.Item);
    if (patch.visible === false || patch.locked) this.selectItems(this.selected.filter((i) => i.layer !== layer));
    this.emit("layers");
    this.commit();
  }

  /** Delete a layer and everything on it. The last layer cannot be deleted. */
  removeLayer(id: string): boolean {
    if (this.layers.length <= 1) return false;
    const index = this.layers.findIndex((l) => l.id === id);
    if (index < 0) return false;
    this.selectItems(this.selected.filter((i) => i.layer?.data?.layerId !== id));
    this.paperLayers.get(id)?.remove();
    this.paperLayers.delete(id);
    this.layers.splice(index, 1);
    if (this.activeLayerId === id) this.activeLayerId = this.layers[Math.max(0, index - 1)].id;
    this.emit("layers");
    this.commit();
    return true;
  }

  moveLayer(id: string, direction: -1 | 1): void {
    const i = this.layers.findIndex((l) => l.id === id);
    const j = i + direction;
    if (i < 0 || j < 0 || j >= this.layers.length) return;
    [this.layers[i], this.layers[j]] = [this.layers[j], this.layers[i]];
    this.syncLayerOrder();
    this.emit("layers");
    this.commit();
  }

  setActiveLayer(id: string): void {
    if (this.layerMeta(id)) {
      this.activeLayerId = id;
      this.emit("layers");
    }
  }

  moveSelectionToLayer(layerId: string): void {
    const target = this.paperLayers.get(layerId);
    if (!target) return;
    for (const item of this.selected) {
      target.addChild(item);
      this.styleItem(item);
    }
    this.commit();
  }

  // ------------------------------------------------------------- doc items
  /** Document items (not UI overlay), in document order. */
  docItems(): paper.Item[] {
    const items: paper.Item[] = [];
    for (const meta of this.layers) {
      const layer = this.paperLayers.get(meta.id);
      if (layer) items.push(...(layer.children as paper.Item[]));
    }
    return items;
  }

  itemById(id: string): paper.Item | undefined {
    return this.docItems().find((i) => i.data?.id === id);
  }

  roleOf(item: paper.Item): LayerRole {
    const id = item.layer?.data?.layerId as string | undefined;
    return (id && this.layerMeta(id)?.role) || "cut";
  }

  pathsOf(items: paper.Item[]): paper.Path[] {
    const out: paper.Path[] = [];
    for (const item of items) {
      if (item instanceof paper.Path) out.push(item);
      else if (item instanceof paper.CompoundPath) out.push(...(item.children as paper.Path[]));
    }
    return out;
  }

  styleItem(item: paper.Item): void {
    if (item.data?.kind === "dim") {
      this.rebuildDimension(item as paper.Group);
      return;
    }
    const style = ROLE_STYLE[this.roleOf(item)];
    item.strokeColor = new paper.Color(style.stroke);
    item.strokeWidth = style.width;
    item.strokeScaling = false;
    item.dashArray = style.dash ?? [];
    // an open path is a line, not a shape: filling it would make it look like a part that gets cut
    const open = item instanceof paper.Path && !item.closed;
    item.fillColor = style.fill && !open ? new paper.Color(style.fill) : null;
    if (item instanceof paper.CompoundPath) item.fillRule = "evenodd";
  }

  /** Register a new path-like item on a layer. */
  addItem(item: paper.Item, options: { layerId?: string; name?: string | null; id?: string; select?: boolean } = {}): paper.Item {
    const layerId = options.layerId && this.paperLayers.has(options.layerId) ? options.layerId : this.activeLayerId;
    const layer = this.paperLayers.get(layerId) ?? [...this.paperLayers.values()][0];
    layer.addChild(item);
    item.data = { ...(item.data ?? {}), id: options.id ?? newId(), kind: item.data?.kind ?? "path", name: options.name ?? item.data?.name ?? null };
    this.styleItem(item);
    if (options.select) this.selectItems([item]);
    return item;
  }

  // ---------------------------------------------------------- dimensions
  createDimension(a: paper.Point, b: paper.Point, offset = 8, label: string | null = null, layerId?: string, id?: string): paper.Group {
    const base = new paper.Path.Line({ from: a, to: b, insert: false });
    const group = new paper.Group({ children: [base], insert: false });
    group.data = { kind: "dim", id: id ?? newId("d"), offset, label };
    // dimension annotations live on a dimension-role layer when one exists
    const dimLayer = layerId ?? this.layers.find((l) => l.role === "dimension")?.id ?? this.activeLayerId;
    this.paperLayers.get(dimLayer)?.addChild(group);
    this.rebuildDimension(group);
    return group;
  }

  rebuildDimension(group: paper.Group): void {
    const base = group.children[0] as paper.Path;
    const a = base.firstSegment.point.clone();
    const b = base.lastSegment.point.clone();
    for (const child of [...group.children].slice(1)) child.remove();
    const style = ROLE_STYLE.dimension;
    const color = new paper.Color(style.stroke);
    base.strokeColor = new paper.Color("rgba(51,65,85,0.35)");
    base.strokeWidth = 1;
    base.strokeScaling = false;
    base.dashArray = [3, 3];

    const v = b.subtract(a);
    const length = v.length;
    if (length < 1e-6) return;
    const u = v.divide(length);
    const n = new paper.Point(-u.y, u.x);
    const offset: number = group.data.offset ?? 8;
    const sign = offset >= 0 ? 1 : -1;
    const off = Math.abs(offset);
    const a2 = a.add(n.multiply(sign * off));
    const b2 = b.add(n.multiply(sign * off));
    const stroke = { strokeColor: color, strokeWidth: 1, strokeScaling: false, insert: false } as const;
    const parts: paper.Item[] = [
      new paper.Path.Line({ from: a.add(n.multiply(sign * 1)), to: a.add(n.multiply(sign * (off + 2))), ...stroke }),
      new paper.Path.Line({ from: b.add(n.multiply(sign * 1)), to: b.add(n.multiply(sign * (off + 2))), ...stroke }),
      new paper.Path.Line({ from: a2, to: b2, ...stroke }),
    ];
    const arrow = (tip: paper.Point, dir: paper.Point) => {
      const back = tip.subtract(dir.multiply(DIM_ARROW_MM));
      const side = new paper.Point(-dir.y, dir.x).multiply(DIM_ARROW_MM / 3.2);
      return new paper.Path({ segments: [tip, back.add(side), back.subtract(side)], closed: true, fillColor: color, strokeColor: color, strokeWidth: 0.5, strokeScaling: false, insert: false });
    };
    parts.push(arrow(a2, u.multiply(-1)), arrow(b2, u));
    const text: string = group.data.label || `${formatMm(length)} mm`;
    const lineMid = a2.add(b2).divide(2);
    let angle = (Math.atan2(v.y, v.x) * 180) / Math.PI;
    if (angle > 90 || angle < -90) angle += 180;
    const label = new paper.PointText({ point: lineMid, content: text, fillColor: color, fontSize: DIM_TEXT_MM, fontFamily: '"IBM Plex Sans", sans-serif', justification: "center", insert: false });
    label.rotate(angle, lineMid);
    // centre the text a clear gap off the dimension line, on the outer side, so the line
    // never strikes through the figure whichever way the dimension is drawn
    label.position = lineMid.add(n.multiply(sign * (0.8 + DIM_TEXT_MM * 0.45)));
    parts.push(label);
    for (const part of parts) group.addChild(part);
  }

  // ------------------------------------------------- document conversion
  private pathToContour(p: paper.Path): DocNode[] {
    return p.segments.map((s) => ({
      x: round4(s.point.x),
      y: round4(s.point.y),
      ix: round4(s.handleIn.x),
      iy: round4(s.handleIn.y),
      ox: round4(s.handleOut.x),
      oy: round4(s.handleOut.y),
    }));
  }

  contourToPath(nodes: DocNode[], closed: boolean): paper.Path {
    const path = new paper.Path({ insert: false });
    for (const n of nodes) {
      path.add(new paper.Segment(new paper.Point(n.x, n.y), new paper.Point(n.ix, n.iy), new paper.Point(n.ox, n.oy)));
    }
    path.closed = closed;
    return path;
  }

  itemToObject(item: paper.Item): DocObject | null {
    const layerId = item.layer?.data?.layerId as string | undefined;
    if (!layerId) return null;
    const id: string = item.data?.id ?? newId();
    if (item.data?.kind === "dim") {
      const base = (item as paper.Group).children[0] as paper.Path;
      const dim: DimensionObject = {
        id,
        type: "dimension",
        layer: layerId,
        a: [round4(base.firstSegment.point.x), round4(base.firstSegment.point.y)],
        b: [round4(base.lastSegment.point.x), round4(base.lastSegment.point.y)],
        offset: round4(item.data.offset ?? 8),
        label: item.data.label ?? null,
      };
      return dim;
    }
    let contours: DocNode[][];
    let closed = true;
    if (item instanceof paper.CompoundPath) {
      contours = (item.children as paper.Path[]).filter((c) => c.segments.length >= 2).map((c) => this.pathToContour(c));
    } else if (item instanceof paper.Path) {
      if (item.segments.length < 2) return null;
      contours = [this.pathToContour(item)];
      closed = item.closed;
    } else {
      return null;
    }
    if (contours.length === 0) return null;
    const obj: PathObject = { id, type: "path", layer: layerId, name: item.data?.name ?? null, closed, contours };
    return obj;
  }

  objectToItem(obj: DocObject): paper.Item {
    if (obj.type === "dimension") {
      const group = this.createDimension(new paper.Point(obj.a[0], obj.a[1]), new paper.Point(obj.b[0], obj.b[1]), obj.offset, obj.label, obj.layer, obj.id);
      return group;
    }
    const paths = obj.contours.map((c) => this.contourToPath(c, obj.closed));
    let item: paper.Item;
    if (paths.length === 1) {
      item = paths[0];
    } else {
      item = new paper.CompoundPath({ children: paths, fillRule: "evenodd", insert: false });
    }
    return this.addItem(item, { layerId: obj.layer, name: obj.name, id: obj.id });
  }

  exportDocument(): DesignDocument {
    const objects: DocObject[] = [];
    for (const item of this.docItems()) {
      const obj = this.itemToObject(item);
      if (obj) objects.push(obj);
    }
    const doc: DesignDocument = { version: 1, unit: "mm", layers: this.layers.map((l) => ({ ...l })), objects };
    // only written when present, so documents without guides round-trip unchanged
    if (this.guides.length) doc.guides = this.guides.map((g) => ({ ...g }));
    return doc;
  }

  loadDocument(doc: DesignDocument, options: { resetHistory?: boolean; fit?: boolean } = {}): void {
    this.handler.cancel();
    this.clearUi();
    this.nodeTargets = [];
    this.selectedSegments = [];
    this.selected = [];
    this.layers = doc.layers.length ? doc.layers.map((l) => ({ ...l })) : defaultLayers();
    this.rebuildLayers();
    if (!this.layerMeta(this.activeLayerId)) this.activeLayerId = this.layers[0].id;
    for (const obj of doc.objects) {
      if (this.paperLayers.has(obj.layer)) this.objectToItem(obj);
    }
    this.normalizeDimensions();
    this.guides = (doc.guides ?? []).map((g) => ({ axis: g.axis, pos: g.pos }));
    this.emit("guides");
    if (options.resetHistory !== false) {
      const state = JSON.stringify(this.exportDocument());
      this.history.reset(state);
      this.savedState = state;
    }
    if (options.fit) this.zoomToFit();
    this.emit("layers");
    this.refreshOverlay();
    this.emitSelection();
    this.emit("change");
  }

  private normalizeDimensions(): void {
    for (const item of this.docItems()) if (item.data?.kind === "dim") this.rebuildDimension(item as paper.Group);
  }

  // -------------------------------------------------------------- history
  get dirty(): boolean {
    return JSON.stringify(this.exportDocument()) !== this.savedState;
  }

  markSaved(): void {
    this.savedState = JSON.stringify(this.exportDocument());
    this.emit("change");
  }

  get canUndo(): boolean {
    return this.history.canUndo;
  }

  get canRedo(): boolean {
    return this.history.canRedo;
  }

  /** Record the current document as an undo step (no-op if unchanged). */
  commit(): void {
    this.normalizeDimensions();
    this.history.push(JSON.stringify(this.exportDocument()));
    this.refreshOverlay();
    this.emit("change");
    this.emitSelection();
  }

  undo(): void {
    this.restore(this.history.undo());
  }

  redo(): void {
    this.restore(this.history.redo());
  }

  private restore(state: string | null): void {
    if (!state) return;
    const ids = this.selected.map((i) => i.data?.id);
    this.loadDocument(JSON.parse(state) as DesignDocument, { resetHistory: false });
    const again = ids.map((id) => (id ? this.itemById(id) : undefined)).filter((i): i is paper.Item => !!i);
    this.selectItems(again);
    this.emit("change");
  }

  // ------------------------------------------------------------ selection
  get selection(): paper.Item[] {
    return this.selected;
  }

  selectItems(items: paper.Item[]): void {
    this.selected = items.filter((i) => i.parent && i.layer?.data?.layerId);
    if (this.toolName === "node") {
      this.nodeTargets = this.pathsOf(this.selected);
      this.selectedSegments = [];
    }
    this.refreshOverlay();
    this.emitSelection();
  }

  addToSelection(item: paper.Item): void {
    this.selectItems(this.selected.includes(item) ? this.selected.filter((i) => i !== item) : [...this.selected, item]);
  }

  clearSelection(): void {
    this.selectedSegments = [];
    if (this.toolName === "node") this.nodeTargets = [];
    this.selectItems([]);
  }

  selectAll(): void {
    this.selectItems(this.docItems().filter((i) => i.visible && !i.parent?.locked));
  }

  selectById(ids: string[]): void {
    this.selectItems(ids.map((id) => this.itemById(id)).filter((i): i is paper.Item => !!i));
  }

  selectionBounds(items = this.selected): paper.Rectangle | null {
    let bounds: paper.Rectangle | null = null;
    for (const item of items) bounds = bounds ? bounds.unite(item.bounds) : item.bounds.clone();
    return bounds;
  }

  emitSelection(): void {
    this.emit("selection", this.selectionInfo());
  }

  selectionInfo(): SelectionInfo {
    const items = this.selected;
    const b = this.selectionBounds();
    const layerIds = new Set(items.map((i) => i.layer?.data?.layerId as string));
    const info: SelectionInfo = {
      count: items.length,
      ids: items.map((i) => i.data?.id as string),
      bounds: b ? { x: b.x, y: b.y, w: b.width, h: b.height } : null,
      name: items.length === 1 ? (items[0].data?.name ?? null) : null,
      layerId: layerIds.size === 1 ? [...layerIds][0] : null,
      mixedLayers: layerIds.size > 1,
      path: null,
      dimension: null,
      selectedNodes: this.selectedSegments.length,
      singleNode: null,
    };
    if (items.length === 1) {
      const item = items[0];
      if (item.data?.kind === "dim") {
        const base = (item as paper.Group).children[0] as paper.Path;
        info.dimension = { offset: item.data.offset ?? 8, label: item.data.label ?? null, length: base.length };
      } else if (item instanceof paper.Path || item instanceof paper.CompoundPath) {
        const paths = this.pathsOf([item]);
        info.path = {
          nodeCount: paths.reduce((n, p) => n + p.segments.length, 0),
          closed: paths.every((p) => p.closed),
          compound: item instanceof paper.CompoundPath,
          area: item instanceof paper.CompoundPath || (item as paper.Path).closed ? this.evenOddArea(item) : 0,
          perimeter: paths.reduce((n, p) => n + p.length, 0),
        };
      }
    }
    if (this.selectedSegments.length === 1) {
      const s = this.selectedSegments[0];
      info.singleNode = { x: round4(s.point.x), y: round4(s.point.y), smooth: this.isSmooth(s) };
    }
    return info;
  }

  isSmooth(s: paper.Segment): boolean {
    const hi = s.handleIn;
    const ho = s.handleOut;
    if (hi.length < 1e-6 || ho.length < 1e-6) return false;
    return Math.abs(hi.normalize().dot(ho.normalize()) + 1) < 1e-3;
  }

  /** Area of a path or compound path using the even-odd rule (holes subtract). */
  evenOddArea(item: paper.Item): number {
    if (item instanceof paper.Path) return Math.abs(item.area);
    if (!(item instanceof paper.CompoundPath)) return 0;
    const children = (item.children as paper.Path[]).filter((c) => c.closed);
    let total = 0;
    for (const child of children) {
      const probe = child.firstSegment.point;
      const depth = children.filter((other) => other !== child && other.contains(probe)).length;
      total += (depth % 2 === 0 ? 1 : -1) * Math.abs(child.area);
    }
    return Math.abs(total);
  }

  private translateSelection(delta: paper.Point): void {
    for (const item of this.selected) item.translate(delta);
  }

  // ----------------------------------------------------------- operations
  deleteSelection(): void {
    if (!this.selected.length) return;
    for (const item of this.selected) item.remove();
    this.selected = [];
    this.nodeTargets = this.nodeTargets.filter((p) => !!p.parent);
    this.selectedSegments = [];
    this.commit();
  }

  nudge(dx: number, dy: number): void {
    if (this.toolName === "node" && this.selectedSegments.length) {
      for (const s of this.selectedSegments) s.point = s.point.add(new paper.Point(dx, dy));
      this.commit();
      return;
    }
    if (!this.selected.length) return;
    this.translateSelection(new paper.Point(dx, dy));
    this.commit();
  }

  duplicateSelection(offset = 5): void {
    if (!this.selected.length) return;
    const clones: paper.Item[] = [];
    for (const item of this.selected) {
      const copy = item.clone({ insert: false, deep: true });
      copy.data = { ...item.data, id: copy.data?.kind === "dim" ? newId("d") : newId() };
      item.layer.addChild(copy);
      copy.translate(new paper.Point(offset, offset));
      clones.push(copy);
    }
    this.selectItems(clones);
    this.commit();
  }

  copySelection(): void {
    this.clipboard = this.selected.map((i) => this.itemToObject(i)).filter((o): o is DocObject => !!o);
    this.hint(this.clipboard.length ? "hint.copied" : "hint.nothingToCopy");
  }

  cutSelection(): void {
    this.copySelection();
    this.deleteSelection();
  }

  pasteClipboard(): void {
    if (!this.clipboard.length) return;
    const pasted: paper.Item[] = [];
    for (const obj of this.clipboard) {
      const copy = JSON.parse(JSON.stringify(obj)) as DocObject;
      copy.id = newId(copy.type === "dimension" ? "d" : "o");
      if (!this.paperLayers.has(copy.layer)) copy.layer = this.activeLayerId;
      pasted.push(this.objectToItem(copy));
    }
    for (const item of pasted) item.translate(new paper.Point(5, 5));
    this.clipboard = this.clipboard.map((o) => shiftObject(o, 5, 5));
    this.selectItems(pasted);
    this.commit();
  }

  flipSelection(axis: "h" | "v"): void {
    const b = this.selectionBounds();
    if (!b) return;
    for (const item of this.selected) item.scale(axis === "h" ? -1 : 1, axis === "v" ? -1 : 1, b.center);
    this.commit();
  }

  rotateSelection(degrees: number, commit = true): void {
    const b = this.selectionBounds();
    if (!b) return;
    for (const item of this.selected) item.rotate(degrees, b.center);
    if (commit) this.commit();
    else this.refreshOverlay();
  }

  /** Mirror copy: duplicate and flip across the right/bottom edge of the selection. */
  mirrorCopy(axis: "h" | "v"): void {
    const b = this.selectionBounds();
    if (!b) return;
    const clones: paper.Item[] = [];
    for (const item of this.selected) {
      const copy = item.clone({ insert: false, deep: true });
      copy.data = { ...item.data, id: copy.data?.kind === "dim" ? newId("d") : newId() };
      item.layer.addChild(copy);
      const pivot = axis === "h" ? new paper.Point(b.right, b.center.y) : new paper.Point(b.center.x, b.bottom);
      copy.scale(axis === "h" ? -1 : 1, axis === "v" ? -1 : 1, pivot);
      clones.push(copy);
    }
    this.selectItems([...this.selected, ...clones]);
    this.commit();
  }

  align(kind: AlignKind): void {
    const items = this.selected;
    const b = this.selectionBounds();
    if (items.length < 2 || !b) return;
    for (const item of items) {
      const ib = item.bounds;
      let dx = 0;
      let dy = 0;
      if (kind === "left") dx = b.left - ib.left;
      if (kind === "right") dx = b.right - ib.right;
      if (kind === "centerH") dx = b.center.x - ib.center.x;
      if (kind === "top") dy = b.top - ib.top;
      if (kind === "bottom") dy = b.bottom - ib.bottom;
      if (kind === "middleV") dy = b.center.y - ib.center.y;
      item.translate(new paper.Point(dx, dy));
    }
    this.commit();
  }

  distribute(axis: "h" | "v"): void {
    const items = [...this.selected];
    if (items.length < 3) return;
    const horizontal = axis === "h";
    items.sort((p, q) => (horizontal ? p.bounds.left - q.bounds.left : p.bounds.top - q.bounds.top));
    const first = items[0].bounds;
    const last = items[items.length - 1].bounds;
    const span = horizontal ? last.right - first.left : last.bottom - first.top;
    const sizes = items.reduce((n, i) => n + (horizontal ? i.bounds.width : i.bounds.height), 0);
    const gap = (span - sizes) / (items.length - 1);
    let cursor = horizontal ? first.left : first.top;
    for (const item of items) {
      const ib = item.bounds;
      const delta = cursor - (horizontal ? ib.left : ib.top);
      item.translate(new paper.Point(horizontal ? delta : 0, horizontal ? 0 : delta));
      cursor += (horizontal ? ib.width : ib.height) + gap;
    }
    this.commit();
  }

  /** Resize / move the selection so its bounds become exactly `target` (mm). */
  setSelectionBounds(target: Partial<Bounds>): void {
    const b = this.selectionBounds();
    if (!b) return;
    const w = target.w ?? b.width;
    const h = target.h ?? b.height;
    if (w <= 0 || h <= 0) return;
    const sx = b.width > 1e-9 ? w / b.width : 1;
    const sy = b.height > 1e-9 ? h / b.height : 1;
    if (Math.abs(sx - 1) > 1e-9 || Math.abs(sy - 1) > 1e-9) {
      for (const item of this.selected) item.scale(sx, sy, b.topLeft);
    }
    const nb = this.selectionBounds()!;
    const dx = (target.x ?? nb.x) - nb.x;
    const dy = (target.y ?? nb.y) - nb.y;
    if (dx || dy) this.translateSelection(new paper.Point(dx, dy));
    this.commit();
  }

  setSelectionName(name: string): void {
    for (const item of this.selected) item.data = { ...item.data, name: name.trim() ? name.trim().slice(0, 100) : null };
    this.commit();
  }

  setDimensionProps(patch: { offset?: number; label?: string | null }): void {
    const item = this.selected.length === 1 && this.selected[0].data?.kind === "dim" ? (this.selected[0] as paper.Group) : null;
    if (!item) return;
    if (patch.offset !== undefined) item.data.offset = patch.offset;
    if (patch.label !== undefined) item.data.label = patch.label && patch.label.trim() ? patch.label.trim() : null;
    this.rebuildDimension(item);
    this.commit();
  }

  combine(): void {
    const items = this.selected.filter((i): i is EditableItem => (i instanceof paper.Path && i.closed) || i instanceof paper.CompoundPath);
    if (items.length < 2) return this.hint("hint.needTwoClosed");
    const parts: paper.Path[] = [];
    for (const item of items) for (const p of this.pathsOf([item])) parts.push(p.clone({ insert: false }) as paper.Path);
    const compound = new paper.CompoundPath({ children: parts, fillRule: "evenodd", insert: false });
    const base = items[0];
    const result = this.addItem(compound, { layerId: base.layer.data.layerId, name: base.data?.name });
    for (const item of items) item.remove();
    this.selectItems([result]);
    this.commit();
  }

  breakApart(): void {
    const compounds = this.selected.filter((i): i is paper.CompoundPath => i instanceof paper.CompoundPath);
    if (!compounds.length) return this.hint("hint.needCompound");
    const out: paper.Item[] = [];
    for (const compound of compounds) {
      const layerId = compound.layer.data.layerId as string;
      for (const child of [...compound.children] as paper.Path[]) {
        const copy = child.clone({ insert: false }) as paper.Path;
        out.push(this.addItem(copy, { layerId }));
      }
      compound.remove();
    }
    this.selectItems(out);
    this.commit();
  }

  booleanOp(op: BooleanOp): void {
    const items = this.docItems().filter(
      (i): i is EditableItem => this.selected.includes(i) && ((i instanceof paper.Path && i.closed) || i instanceof paper.CompoundPath),
    );
    if (items.length < 2) return this.hint("hint.needTwoClosed");
    // z-order: lowest first. Subtract = lowest minus every item above it.
    let result: paper.PathItem = items[0];
    for (const other of items.slice(1)) {
      const next: paper.PathItem = result[op](other, { insert: false });
      if (result !== items[0]) result.remove();
      result = next;
    }
    if (result.bounds.width * result.bounds.height < 1e-6 && Math.abs((result as EditableItem).length ?? 0) < 1e-6) {
      result.remove();
      return this.hint("hint.emptyResult");
    }
    const base = items[0];
    const layerId = base.layer.data.layerId as string;
    const name = base.data?.name ?? null;
    for (const item of items) item.remove();
    const added = this.addItem(result as paper.Item, { layerId, name });
    this.selectItems([added]);
    this.commit();
  }

  /** Replace the (single) selected closed shape with polygon contours, e.g. from the offset endpoint. */
  replaceSelectionWithContours(contours: DocNode[][], keepOriginal = false): void {
    const base = this.selected[0];
    if (!base || !contours.length) return;
    const layerId = base.layer.data.layerId as string;
    const paths = contours.map((c) => this.contourToPath(c, true));
    const item: paper.Item = paths.length === 1 ? paths[0] : new paper.CompoundPath({ children: paths, fillRule: "evenodd", insert: false });
    const added = this.addItem(item, { layerId, name: base.data?.name ? `${base.data.name} (offset)` : null });
    if (!keepOriginal) base.remove();
    this.selectItems([added]);
    this.commit();
  }

  /** Contours of the selected closed shape, for server-side offsetting. */
  selectedContours(): DocNode[][] | null {
    if (this.selected.length !== 1) return null;
    const item = this.selected[0];
    if (item instanceof paper.Path && item.closed) return [this.pathToContour(item)];
    if (item instanceof paper.CompoundPath) return (item.children as paper.Path[]).filter((c) => c.closed).map((c) => this.pathToContour(c));
    return null;
  }

  // ---------------------------------------------------------------- nodes
  deleteSelectedNodes(): void {
    if (!this.selectedSegments.length) return;
    for (const seg of [...this.selectedSegments]) {
      const path = seg.path;
      if (!path) continue;
      if (path.segments.length <= (path.closed ? 3 : 2)) continue; // keep the shape valid
      seg.remove();
    }
    this.selectedSegments = [];
    this.commit();
  }

  /** Insert a node in the middle of every curve between two adjacent selected nodes. */
  insertNodes(): void {
    const picked = new Set(this.selectedSegments);
    const toSplit: paper.Curve[] = [];
    for (const seg of this.selectedSegments) {
      const next = seg.next;
      if (seg.curve && next && picked.has(next)) toSplit.push(seg.curve);
    }
    if (!toSplit.length) return this.hint("hint.selectAdjacentNodes");
    for (const curve of toSplit) curve.divideAtTime(0.5);
    this.selectedSegments = [];
    this.commit();
  }

  setNodeType(kind: "smooth" | "corner"): void {
    for (const seg of this.selectedSegments) {
      if (kind === "corner") {
        seg.handleIn = new paper.Point(0, 0);
        seg.handleOut = new paper.Point(0, 0);
      } else {
        seg.smooth({ type: "catmull-rom", factor: 0.5 });
      }
    }
    this.commit();
  }

  toggleClosed(): void {
    for (const path of this.nodeTargets) {
      path.closed = !path.closed;
      this.styleItem(path.parent instanceof paper.CompoundPath ? path.parent : path);
    }
    this.commit();
  }

  reversePaths(): void {
    for (const path of this.nodeTargets) path.reverse();
    this.selectedSegments = [];
    this.commit();
  }

  simplifyPaths(tolerance = 0.2): void {
    for (const path of this.nodeTargets) path.simplify(tolerance);
    this.selectedSegments = [];
    this.commit();
  }

  /** Replace curves by straight segments (polygon), useful before CNC / for faceted designs. */
  flattenPaths(tolerance = 0.1): void {
    for (const path of this.nodeTargets) path.flatten(tolerance);
    this.selectedSegments = [];
    this.commit();
  }

  /**
   * Round (fillet) or cut (chamfer) every selected corner node whose two edges are straight.
   * `size` is the radius, or the chamfer length on each edge. When both ends of an edge are
   * treated, each may use at most half of it. Corners that cannot take the size are left as
   * they are and reported.
   */
  roundCorners(kind: "fillet" | "chamfer", size: number): CornerReport {
    const report: CornerReport = { done: 0, skipped: {} };
    const skip = (why: CornerError | "curvedEdge") => (report.skipped[why] = (report.skipped[why] ?? 0) + 1);
    const straight = (h: paper.Point) => h.length < 1e-9;
    const picked = new Set(this.selectedSegments);
    const jobs: { seg: paper.Segment; nodes: DocNode[] }[] = [];
    for (const seg of this.selectedSegments) {
      const path = seg.path;
      const prev = seg.previous;
      const next = seg.next;
      if (!path || !prev || !next) {
        skip("notCorner"); // open path end: there is no corner
        continue;
      }
      if (!straight(seg.handleIn) || !straight(seg.handleOut) || !straight(prev.handleOut) || !straight(next.handleIn)) {
        skip("curvedEdge");
        continue;
      }
      const P = (pt: paper.Point): [number, number] => [pt.x, pt.y];
      const lenPrev = seg.point.getDistance(prev.point) / (picked.has(prev) ? 2 : 1);
      const lenNext = seg.point.getDistance(next.point) / (picked.has(next) ? 2 : 1);
      const result =
        kind === "fillet"
          ? filletCorner(P(prev.point), P(seg.point), P(next.point), size, lenPrev, lenNext)
          : chamferCorner(P(prev.point), P(seg.point), P(next.point), size, lenPrev, lenNext);
      if (!result.ok) skip(result.error);
      else jobs.push({ seg, nodes: result.nodes });
    }
    // computed first from the original geometry, then applied (indices shift as nodes are added)
    for (const { seg, nodes } of jobs) {
      const path = seg.path;
      const index = seg.index;
      path.removeSegment(index);
      path.insertSegments(
        index,
        nodes.map((n) => new paper.Segment(new paper.Point(n.x, n.y), new paper.Point(n.ix, n.iy), new paper.Point(n.ox, n.oy))),
      );
      report.done += 1;
    }
    this.selectedSegments = [];
    if (report.done) this.commit();
    else this.refreshOverlay();
    this.emitSelection();
    return report;
  }

  /** Add open or closed contours as one new object (compound when several), selected. */
  addContours(contours: DocNode[][], options: { closed: boolean; layerId?: string; name?: string | null }): paper.Item | null {
    const usable = contours.filter((c) => c.length >= 2);
    if (!usable.length) return null;
    const paths = usable.map((c) => this.contourToPath(c, options.closed));
    const item: paper.Item = paths.length === 1 ? paths[0] : new paper.CompoundPath({ children: paths, fillRule: "evenodd", insert: false });
    const added = this.addItem(item, { layerId: options.layerId, name: options.name ?? null });
    this.selectItems([added]);
    this.commit();
    return added;
  }

  /**
   * Insert library parts (already placed, in mm), each on the first layer with its role. A missing
   * grind layer is created ("Émouture"); other roles fall back to the active layer. One undo step.
   */
  insertParts(parts: ShapePart[]): number {
    const added: paper.Item[] = [];
    for (const part of parts) {
      const contours = part.contours.filter((c) => c.length >= 2);
      if (!contours.length) continue;
      let layerId = this.layerWithRole(part.role);
      if (!layerId && part.role === "grind") layerId = this.createLayer("Émouture", "grind").id;
      const paths = contours.map((c) => this.contourToPath(c, part.closed));
      const item: paper.Item = paths.length === 1 ? paths[0] : new paper.CompoundPath({ children: paths, fillRule: "evenodd", insert: false });
      added.push(this.addItem(item, { layerId: layerId ?? this.activeLayerId, name: part.name || null }));
    }
    if (!added.length) return 0;
    this.selectItems(added);
    this.commit();
    return added.length;
  }

  /** First layer with this role, if any. */
  layerWithRole(role: LayerRole): string | undefined {
    return this.layers.find((l) => l.role === role)?.id;
  }

  /** A row of round holes, on the first "hole" layer (or the active one). One undo step. */
  addHoles(pattern: HolePattern): number {
    const r = pattern.diameter / 2;
    if (!(r > 0) || !Number.isFinite(r)) return 0;
    const layerId = this.layerWithRole("hole") ?? this.activeLayerId;
    const added: paper.Item[] = [];
    for (const [cx, cy] of holeCentres(pattern)) {
      added.push(this.addItem(this.contourToPath(circleNodes(cx, cy, r), true), { layerId, name: `Ø ${formatMm(pattern.diameter)}` }));
    }
    this.selectItems(added);
    this.commit();
    return added.length;
  }

  /** Let the active tool take a typed length / angle (pen: next point). */
  toolNumeric(length: number, angle: number): boolean {
    return this.handler.numeric?.(length, angle) ?? false;
  }

  setSingleNodePosition(x: number, y: number): void {
    if (this.selectedSegments.length !== 1) return;
    this.selectedSegments[0].point = new paper.Point(x, y);
    this.commit();
  }

  // ----------------------------------------------------------------- SVG
  /** Import path geometry from SVG text. Returns the number of imported shapes. */
  importSvg(svg: string): number {
    const scale = detectSvgScaleToMm(svg);
    const imported = this.project.importSVG(svg, { expandShapes: true, insert: false }) as paper.Item;
    const shapes: EditableItem[] = [];
    const walk = (item: paper.Item) => {
      if (item instanceof paper.Path || item instanceof paper.CompoundPath) {
        shapes.push(item);
      } else if (item.children) {
        for (const child of [...item.children]) walk(child);
      }
    };
    walk(imported);
    const added: paper.Item[] = [];
    for (const shape of shapes) {
      // bake all ancestor transforms into the geometry and scale to millimetres
      const copy = shape.clone({ insert: false }) as EditableItem;
      copy.transform(shape.globalMatrix);
      copy.scale(scale, new paper.Point(0, 0));
      if (copy instanceof paper.Path && copy.segments.length < 2) continue;
      added.push(this.addItem(copy, { name: shape.name || null }));
    }
    imported.remove();
    if (added.length) {
      const b = this.selectionBounds(added)!;
      for (const item of added) item.translate(new paper.Point(-b.x, -b.y));
      this.selectItems(added);
      this.commit();
      this.zoomToFit();
    }
    return added.length;
  }

  // ----------------------------------------------------------------- grid
  /** Any step from MIN_GRID_MM to MAX_GRID_MM (kept to 4 decimals, like every coordinate). */
  setGridSize(size: number): void {
    if (Number.isFinite(size) && size >= MIN_GRID_MM && size <= MAX_GRID_MM) this.gridSize = round4(size);
    this.emit("view");
  }

  /** Grid-snapped coordinate along one axis. */
  snapAxis(value: number): number {
    return this.snapOptions.grid ? round4(Math.round(value / this.gridSize) * this.gridSize) : round4(value);
  }

  // ---------------------------------------------------------------- guides
  /** Index of the guide within a few pixels of `p`, or -1. */
  guideAt(p: paper.Point, tolerancePx = 4): number {
    let best = -1;
    let bestDist = this.px(tolerancePx);
    this.guides.forEach((g, i) => {
      const d = Math.abs((g.axis === "x" ? p.x : p.y) - g.pos);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    });
    return best;
  }

  addGuide(axis: Guide["axis"], pos: number): void {
    this.previewGuide = null;
    if (!Number.isFinite(pos)) return;
    this.guides.push({ axis, pos: round4(pos) });
    this.emit("guides");
    this.commit();
  }

  /** Move a guide; `commit` = record it as an undo step (false while dragging). */
  moveGuide(index: number, pos: number, commit = true): void {
    const g = this.guides[index];
    if (!g || !Number.isFinite(pos)) return;
    g.pos = round4(pos);
    this.emit("guides");
    if (commit) this.commit();
  }

  removeGuide(index: number): void {
    if (index < 0 || index >= this.guides.length) return;
    this.guides.splice(index, 1);
    this.emit("guides");
    this.commit();
  }

  clearGuides(): void {
    if (!this.guides.length) return;
    this.guides = [];
    this.emit("guides");
    this.commit();
  }

  /** Is this world point under one of the rulers? (a guide dropped there is deleted) */
  overRuler(p: paper.Point, rulerPx: number): boolean {
    const v = this.view.projectToView(p);
    return v.x < rulerPx || v.y < rulerPx;
  }

  // -------------------------------------------------------- reference image
  get background(): BackgroundState | null {
    return this.bg ? { ...this.bg } : null;
  }

  /** Replace (or remove, with null) the reference image. Not an undo step: it is not part of the document. */
  setBackground(state: BackgroundState | null): void {
    this.raster?.remove();
    this.raster = null;
    this.bg = state ? { ...state } : null;
    if (state) {
      const raster = new paper.Raster({ insert: false });
      raster.onLoad = () => {
        if (this.raster !== raster || !this.bg) return;
        this.bg.pixelWidth = raster.width;
        this.bg.pixelHeight = raster.height;
        this.applyBackground();
        this.emit("background");
      };
      raster.source = state.image;
      this.bgLayer.addChild(raster);
      this.raster = raster;
      this.applyBackground();
    }
    this.emit("background");
  }

  updateBackground(patch: Partial<Omit<BackgroundState, "image">>): void {
    if (!this.bg) return;
    Object.assign(this.bg, patch);
    this.applyBackground();
    this.emit("background");
  }

  /** Scale (and optionally straighten) the image so the two picked points end up `realMm` apart. */
  calibrateBackground(a: [number, number], b: [number, number], realMm: number, straighten: Straighten, moveAToOrigin: boolean): void {
    if (!this.bg) return;
    this.updateBackground({ ...calibrate(this.bg, a, b, realMm, straighten, moveAToOrigin), calibrated: true });
  }

  /**
   * Correct the photo's perspective: the four picked corners (document mm, click order) are those
   * of a `width` × `height` mm rectangle lying in the photo's plane. The photo is resampled and
   * replaced, calibrated, corner 1 staying where it was (or moved to 0;0). Null when the four
   * points cannot be the corners of a rectangle (crossed or aligned) or the image is not loaded.
   */
  async rectifyBackground(corners: [number, number][], width: number, height: number, moveToOrigin: boolean): Promise<RectifyPlan | null> {
    const bg = this.bg;
    if (!bg?.pixelWidth || !bg.pixelHeight || !(width > 0) || !(height > 0)) return null;
    const pixels = corners.map((c) => docToPixel(bg, bg.pixelWidth!, bg.pixelHeight!, c));
    const plan = planRectify(pixels, rectangleTargets(corners, width, height), bg.pixelWidth, bg.pixelHeight, { maxPx: MAX_IMAGE_PX });
    if (!plan) return null;
    const image = await rectifyImage(bg.image, plan);
    if (this.bg !== bg) return null; // replaced meanwhile
    const placement = rectifiedPlacement(plan, moveToOrigin ? [0, 0] : corners[0]);
    this.setBackground({ ...bg, image, ...placement, calibrated: true, pixelWidth: undefined, pixelHeight: undefined });
    return plan;
  }

  private applyBackground(): void {
    const bg = this.bg;
    const r = this.raster;
    if (!bg || !r) return;
    r.visible = bg.visible;
    r.opacity = bg.opacity;
    if (!r.width || !r.height) return; // not decoded yet: onLoad places it
    // Raster content is centred on its local origin: scale pixels to mm, rotate, then move the centre.
    r.matrix = new paper.Matrix()
      .translate(new paper.Point(bg.cx, bg.cy))
      .rotate(bg.rotation_deg, new paper.Point(0, 0))
      .scale(bg.width_mm / r.width, bg.height_mm / r.height, new paper.Point(0, 0));
  }

  // --------------------------------------------------------------- measure
  get measurement(): Measurement | null {
    return this.lastMeasure;
  }

  setMeasurement(a: paper.Point | null, b: paper.Point | null): void {
    this.lastMeasure = a && b ? measure(a, b) : null;
    this.emit("measure", this.lastMeasure);
  }

  /** Turn the last measurement into a dimension annotation (one undo step). */
  measurementToDimension(): boolean {
    const m = this.lastMeasure;
    if (!m || m.distance < 0.01) return false;
    const group = this.createDimension(new paper.Point(m.a[0], m.a[1]), new paper.Point(m.b[0], m.b[1]));
    this.selectItems([group]);
    this.commit();
    return true;
  }
}

function shiftObject(obj: DocObject, dx: number, dy: number): DocObject {
  const copy = JSON.parse(JSON.stringify(obj)) as DocObject;
  if (copy.type === "path") {
    for (const contour of copy.contours) for (const n of contour) { n.x += dx; n.y += dy; }
  } else {
    copy.a = [copy.a[0] + dx, copy.a[1] + dy];
    copy.b = [copy.b[0] + dx, copy.b[1] + dy];
  }
  return copy;
}

function normalizeAngle(deg: number): number {
  let a = Math.round(deg * 10) / 10;
  while (a <= -180) a += 360;
  while (a > 180) a -= 360;
  return a === 0 ? 0 : a; // no "-0"
}

/** Distance, components and angle between two points (angle read with y up, as on a drawing). */
export function measure(a: paper.Point, b: paper.Point): Measurement {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return {
    a: [round4(a.x), round4(a.y)],
    b: [round4(b.x), round4(b.y)],
    distance: Math.hypot(dx, dy),
    dx,
    dy,
    angle: normalizeAngle((Math.atan2(-dy, dx) * 180) / Math.PI),
  };
}

export function formatMm(value: number): string {
  return (Math.round(value * 100) / 100).toString();
}

/** Scale factor from the SVG's own user units to millimetres. */
export function detectSvgScaleToMm(svg: string): number {
  const root = /<svg\b[^>]*>/i.exec(svg)?.[0] ?? "";
  const attr = (name: string) => new RegExp(`\\b${name}\\s*=\\s*["']([^"']+)["']`, "i").exec(root)?.[1];
  const parse = (v: string | undefined) => {
    const m = v ? /^\s*([0-9.]+)\s*(mm|cm|in|pt|pc|px)?\s*$/i.exec(v) : null;
    return m ? { n: parseFloat(m[1]), unit: (m[2] ?? "px").toLowerCase() } : null;
  };
  const toMm = { mm: 1, cm: 10, in: 25.4, pt: 25.4 / 72, pc: 25.4 / 6, px: 25.4 / 96 } as const;
  const width = parse(attr("width"));
  const viewBox = attr("viewBox")?.split(/[\s,]+/).map(Number);
  if (width && viewBox && viewBox.length === 4 && viewBox[2] > 0) {
    return (width.n * toMm[width.unit as keyof typeof toMm]) / viewBox[2];
  }
  if (width) return toMm[width.unit as keyof typeof toMm];
  return 25.4 / 96;
}
