/** Parametric shape library: knifemaking parts built from exact Bézier nodes (mm, y down),
 *  each drawn from (0, 0) at its top-left, then inserted where the user wants it.
 *  Also turns another design into a reusable shape ("my templates"). */

import { arcNodes, circleNodes } from "./drafting";
import type { DesignDocument, DocNode, LayerRole } from "./types";

export interface ShapePart {
  role: LayerRole;
  name: string;
  closed: boolean;
  contours: DocNode[][];
}

export interface ShapeParam {
  key: string;
  /** i18n key */
  label: string;
  value: number;
  min: number;
  max: number;
  /** whole number (a count) */
  integer?: boolean;
  /** a share in %, not a length (shown as is, whatever the display unit) */
  percent?: boolean;
}

/** a length parameter follows the editor's display unit (mm or in) */
export const isLengthParam = (p: ShapeParam) => !p.integer && !p.percent;

export interface ShapeDef {
  key: string;
  /** i18n key */
  label: string;
  params: ShapeParam[];
  build: (p: Record<string, number>) => ShapePart[];
}

const round4 = (v: number) => Math.round(v * 10000) / 10000;
const n = (x: number, y: number, ix = 0, iy = 0, ox = 0, oy = 0): DocNode => ({
  x: round4(x),
  y: round4(y),
  ix: round4(ix),
  iy: round4(iy),
  ox: round4(ox),
  oy: round4(oy),
});

/** Rectangle with round corners (radius clamped to half the shorter side), clockwise from the top. */
export function roundedRect(x: number, y: number, w: number, h: number, r: number): DocNode[] {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2));
  if (rr === 0) return [n(x, y), n(x + w, y), n(x + w, y + h), n(x, y + h)];
  const corner = (cx: number, cy: number, start: number) => arcNodes([cx, cy], rr, start, Math.PI / 2);
  const q = Math.PI / 2;
  const pieces = [corner(x + w - rr, y + rr, -q), corner(x + w - rr, y + h - rr, 0), corner(x + rr, y + h - rr, q), corner(x + rr, y + rr, 2 * q)];
  const out: DocNode[] = [];
  for (const arc of pieces) {
    for (const node of arc) {
      const last = out[out.length - 1];
      // a full half-side radius makes neighbouring arcs meet: merge the shared node
      if (last && Math.abs(last.x - node.x) < 1e-9 && Math.abs(last.y - node.y) < 1e-9) {
        out[out.length - 1] = { ...last, ox: node.ox, oy: node.oy };
      } else out.push(node);
    }
  }
  const first = out[0];
  const last = out[out.length - 1];
  if (Math.abs(last.x - first.x) < 1e-9 && Math.abs(last.y - first.y) < 1e-9) {
    out[0] = { ...first, ix: last.ix, iy: last.iy };
    out.pop();
  }
  return out;
}

/** Ellipse through its four extreme points (same 4/3·tan(π/8) handles as the circle). */
export function ellipse(cx: number, cy: number, rx: number, ry: number): DocNode[] {
  const k = (4 / 3) * Math.tan(Math.PI / 8);
  return [n(cx + rx, cy, 0, -k * ry, 0, k * ry), n(cx, cy + ry, k * rx, 0, -k * rx, 0), n(cx - rx, cy, 0, k * ry, 0, -k * ry), n(cx, cy - ry, -k * rx, 0, k * rx, 0)];
}

/** Rounded slot (stadium) centred on (cx, cy). */
function slot(cx: number, cy: number, length: number, width: number): DocNode[] {
  const l = Math.max(length, width);
  return roundedRect(cx - l / 2, cy - width / 2, l, width, width / 2);
}

const hole = (cx: number, cy: number, d: number, name: string): ShapePart => ({ role: "hole", name, closed: true, contours: [circleNodes(cx, cy, d / 2)] });

/** Pin holes evenly spread along y = cy, `inset` from both ends of a part `length` long. */
function pinRow(count: number, length: number, inset: number, cy: number, d: number): ShapePart[] {
  const c = Math.max(0, Math.round(count));
  if (!c || !(d > 0)) return [];
  if (c === 1) return [hole(length / 2, cy, d, "Perçage 1")];
  const step = (length - 2 * inset) / (c - 1);
  return Array.from({ length: c }, (_, i) => hole(inset + step * i, cy, d, `Perçage ${i + 1}`));
}

export const SHAPES: ShapeDef[] = [
  {
    key: "handleScale",
    label: "shape.handleScale",
    params: [
      { key: "length", label: "shape.p.length", value: 110, min: 10, max: 600 },
      { key: "width", label: "shape.p.width", value: 25, min: 5, max: 200 },
      { key: "radius", label: "shape.p.cornerRadius", value: 6, min: 0, max: 100 },
      { key: "pins", label: "shape.p.pins", value: 2, min: 0, max: 8, integer: true },
      { key: "pinD", label: "shape.p.pinD", value: 4.76, min: 0.5, max: 20 },
      { key: "inset", label: "shape.p.inset", value: 14, min: 0, max: 300 },
    ],
    build: (p) => [
      { role: "cut", name: "Plaquette", closed: true, contours: [roundedRect(0, 0, p.length, p.width, p.radius)] },
      ...pinRow(p.pins, p.length, p.inset, p.width / 2, p.pinD),
    ],
  },
  {
    key: "ovalGuard",
    label: "shape.ovalGuard",
    params: [
      { key: "width", label: "shape.p.width", value: 42, min: 5, max: 300 },
      { key: "height", label: "shape.p.height", value: 16, min: 3, max: 200 },
      { key: "slotL", label: "shape.p.slotL", value: 18, min: 1, max: 200 },
      { key: "slotW", label: "shape.p.slotW", value: 4.5, min: 0.5, max: 50 },
    ],
    build: (p) => [
      { role: "cut", name: "Garde", closed: true, contours: [ellipse(p.width / 2, p.height / 2, p.width / 2, p.height / 2)] },
      { role: "hole", name: "Fente de soie", closed: true, contours: [slot(p.width / 2, p.height / 2, p.slotL, p.slotW)] },
    ],
  },
  {
    key: "straightGuard",
    label: "shape.straightGuard",
    params: [
      { key: "width", label: "shape.p.width", value: 60, min: 5, max: 300 },
      { key: "height", label: "shape.p.height", value: 12, min: 3, max: 200 },
      { key: "radius", label: "shape.p.cornerRadius", value: 6, min: 0, max: 100 },
      { key: "slotL", label: "shape.p.slotL", value: 18, min: 1, max: 200 },
      { key: "slotW", label: "shape.p.slotW", value: 4.5, min: 0.5, max: 50 },
    ],
    build: (p) => [
      { role: "cut", name: "Garde", closed: true, contours: [roundedRect(0, 0, p.width, p.height, p.radius)] },
      { role: "hole", name: "Fente de soie", closed: true, contours: [slot(p.width / 2, p.height / 2, p.slotL, p.slotW)] },
    ],
  },
  {
    key: "washer",
    label: "shape.washer",
    params: [
      { key: "outer", label: "shape.p.outerD", value: 20, min: 1, max: 300 },
      { key: "inner", label: "shape.p.innerD", value: 6.35, min: 0, max: 299 },
    ],
    build: (p) => [
      { role: "cut", name: "Rondelle", closed: true, contours: [circleNodes(p.outer / 2, p.outer / 2, p.outer / 2)] },
      ...(p.inner > 0 && p.inner < p.outer ? [hole(p.outer / 2, p.outer / 2, p.inner, "Alésage")] : []),
    ],
  },
  {
    key: "tangSlot",
    label: "shape.tangSlot",
    params: [
      { key: "length", label: "shape.p.slotL", value: 18, min: 1, max: 200 },
      { key: "width", label: "shape.p.slotW", value: 4.5, min: 0.5, max: 50 },
    ],
    build: (p) => [{ role: "hole", name: "Fente de soie", closed: true, contours: [slot(Math.max(p.length, p.width) / 2, p.width / 2, p.length, p.width)] }],
  },
  {
    key: "dropPoint",
    label: "shape.dropPoint",
    params: [
      { key: "blade", label: "shape.p.bladeLength", value: 112, min: 30, max: 400 },
      { key: "height", label: "shape.p.bladeHeight", value: 32, min: 10, max: 120 },
      { key: "tang", label: "shape.p.tangLength", value: 70, min: 0, max: 300 },
      { key: "tangW", label: "shape.p.tangWidth", value: 16, min: 3, max: 100 },
      { key: "pins", label: "shape.p.pins", value: 2, min: 0, max: 6, integer: true },
      { key: "pinD", label: "shape.p.pinD", value: 5, min: 0.5, max: 20 },
      { key: "grind", label: "shape.p.grindHeight", value: 50, min: 0, max: 100, percent: true },
    ],
    build: (p) => dropPoint(p),
  },
  {
    key: "wharncliffe",
    label: "shape.wharncliffe",
    params: [
      { key: "blade", label: "shape.p.bladeLength", value: 90, min: 30, max: 400 },
      { key: "height", label: "shape.p.bladeHeight", value: 25, min: 10, max: 120 },
      { key: "tang", label: "shape.p.tangLength", value: 60, min: 0, max: 300 },
      { key: "tangW", label: "shape.p.tangWidth", value: 14, min: 3, max: 100 },
      { key: "pins", label: "shape.p.pins", value: 2, min: 0, max: 6, integer: true },
      { key: "pinD", label: "shape.p.pinD", value: 4, min: 0.5, max: 20 },
      { key: "grind", label: "shape.p.grindHeight", value: 45, min: 0, max: 100, percent: true },
    ],
    build: (p) => wharncliffe(p),
  },
  bladeShape("clipPoint", 100, 30, 65, 15, 2, 4.76, 50, clipPoint),
  bladeShape("spearPoint", 95, 26, 60, 14, 2, 4.76, 50, spearPoint),
  bladeShape("tanto", 110, 30, 70, 16, 2, 5, 55, tanto),
  bladeShape("sheepsfoot", 85, 24, 60, 14, 2, 4, 45, sheepsfoot),
  bladeShape("trailingPoint", 105, 30, 70, 16, 2, 5, 50, trailingPoint),
  bladeShape("skinner", 90, 34, 70, 16, 3, 4.76, 55, skinner),
  bladeShape("bowie", 200, 40, 110, 22, 3, 6.35, 50, bowie),
  bladeShape("paring", 85, 20, 70, 12, 2, 3.18, 60, dropPointBlade),
  bladeShape("gyuto", 210, 48, 110, 22, 3, 4.76, 70, gyuto),
  bladeShape("santoku", 170, 46, 105, 22, 3, 4.76, 70, santoku),
  bladeShape("nakiri", 165, 50, 105, 22, 3, 4.76, 70, nakiri),
  bladeShape("kiritsuke", 240, 46, 115, 22, 3, 4.76, 70, kiritsuke),
];

/**
 * A blade profile with the same parameters as the drop point: blade length and height, tang,
 * pins, grind height. `outline` gives the nodes from the spine at the ricasso (t, 0), round the
 * tip, back to the edge at the ricasso (t, h); the tang and pins are added around it.
 */
function bladeShape(
  key: string,
  blade: number,
  height: number,
  tangLength: number,
  tangW: number,
  pins: number,
  pinD: number,
  grind: number,
  outline: (t: number, l: number, h: number) => { nodes: DocNode[]; tip: [number, number] },
): ShapeDef {
  return {
    key,
    label: `shape.${key}`,
    params: [
      { key: "blade", label: "shape.p.bladeLength", value: blade, min: 30, max: 400 },
      { key: "height", label: "shape.p.bladeHeight", value: height, min: 10, max: 120 },
      { key: "tang", label: "shape.p.tangLength", value: tangLength, min: 0, max: 300 },
      { key: "tangW", label: "shape.p.tangWidth", value: tangW, min: 3, max: 100 },
      { key: "pins", label: "shape.p.pins", value: pins, min: 0, max: 6, integer: true },
      { key: "pinD", label: "shape.p.pinD", value: pinD, min: 0.5, max: 20 },
      { key: "grind", label: "shape.p.grindHeight", value: grind, min: 0, max: 100, percent: true },
    ],
    build: (p) => {
      const { blade: l, height: h, tang: t, tangW: tw } = p;
      const tg = tang(t, h, Math.min(tw, h));
      const { nodes, tip } = outline(t, l, h);
      const grindTip: [number, number] = [tip[0] - Math.min(2, l * 0.02), tip[1]];
      return [
        { role: "cut", name: "Lame", closed: true, contours: [dedupe([...tg.nodesFront, ...nodes, ...tg.nodesBack])] },
        ...grindLine(t, grindTip[0] - t, h, p.grind, grindTip),
        ...(t > 0 ? pinRow(p.pins, t, Math.min(t * 0.22, t / 2), tg.top + Math.min(tw, h) / 2, p.pinD) : []),
      ];
    },
  };
}

// Each outline runs spine → tip → edge, y down (spine at 0, edge at h). Handles are relative.

function dropPointBlade(t: number, l: number, h: number) {
  const tip: [number, number] = [t + l, h * 0.55];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.7, 0, 0, 0, l * 0.18, 0), n(tip[0], tip[1], -l * 0.06, -h * 0.4, -l * 0.06, h * 0.3), n(t + l * 0.5, h, l * 0.25, 0, 0, 0), n(t, h)],
  };
}

function clipPoint(t: number, l: number, h: number) {
  // straight spine, then a concave clip down to a tip a third of the way down
  const tip: [number, number] = [t + l, h * 0.32];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.62, 0, 0, 0, l * 0.16, h * 0.2), n(tip[0], tip[1], -l * 0.1, -h * 0.02, -l * 0.04, h * 0.38), n(t + l * 0.55, h, l * 0.24, 0, 0, 0), n(t, h)],
  };
}

function spearPoint(t: number, l: number, h: number) {
  const tip: [number, number] = [t + l, h * 0.5];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.5, 0, 0, 0, l * 0.28, 0), n(tip[0], tip[1], -l * 0.08, -h * 0.32, -l * 0.08, h * 0.32), n(t + l * 0.5, h, l * 0.28, 0, 0, 0), n(t, h)],
  };
}

function tanto(t: number, l: number, h: number) {
  // straight edge to a secondary point, then a straight front edge up to the tip
  const tip: [number, number] = [t + l, h * 0.12];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.72, 0), n(tip[0], tip[1]), n(t + l * 0.86, h), n(t, h)],
  };
}

function sheepsfoot(t: number, l: number, h: number) {
  // straight edge, the spine rolls down to meet it
  const tip: [number, number] = [t + l, h];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.55, 0, 0, 0, l * 0.36, 0), n(tip[0], tip[1], 0, -h * 0.7, 0, 0), n(t, h)],
  };
}

function trailingPoint(t: number, l: number, h: number) {
  // the tip rises above the spine line, long sweeping belly
  const tip: [number, number] = [t + l, -h * 0.15];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.5, h * 0.05, -l * 0.2, 0, l * 0.25, 0), n(tip[0], tip[1], -l * 0.12, h * 0.05, -l * 0.05, h * 0.45), n(t + l * 0.45, h, l * 0.3, 0, 0, 0), n(t, h)],
  };
}

function skinner(t: number, l: number, h: number) {
  // broad belly for long sweeping cuts, tip well below the spine
  const tip: [number, number] = [t + l, h * 0.42];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.45, 0, 0, 0, l * 0.3, h * 0.05), n(tip[0], tip[1], -l * 0.08, -h * 0.3, -l * 0.02, h * 0.42), n(t + l * 0.38, h, l * 0.36, 0, 0, 0), n(t, h)],
  };
}

function bowie(t: number, l: number, h: number) {
  // long concave clip starting before the middle, generous belly
  const tip: [number, number] = [t + l, h * 0.28];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.5, 0, 0, 0, l * 0.24, h * 0.24), n(tip[0], tip[1], -l * 0.12, -h * 0.04, -l * 0.05, h * 0.4), n(t + l * 0.55, h, l * 0.26, 0, 0, 0), n(t, h)],
  };
}

function gyuto(t: number, l: number, h: number) {
  // chef's knife: flat heel, curve rising to a tip near the spine
  const tip: [number, number] = [t + l, h * 0.22];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.6, h * 0.03, -l * 0.3, 0, l * 0.25, 0), n(tip[0], tip[1], -l * 0.1, -h * 0.1, -l * 0.12, h * 0.42), n(t + l * 0.62, h, l * 0.2, 0, 0, 0), n(t, h)],
  };
}

function santoku(t: number, l: number, h: number) {
  // sheepsfoot-like nose dropping to a tip just above the edge, nearly flat edge
  const tip: [number, number] = [t + l, h * 0.9];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.55, 0, 0, 0, l * 0.32, h * 0.04), n(tip[0], tip[1], -l * 0.02, -h * 0.55, -l * 0.04, h * 0.05), n(t + l * 0.6, h, l * 0.25, 0, 0, 0), n(t, h)],
  };
}

function nakiri(t: number, l: number, h: number) {
  // rectangular vegetable cleaver, slightly rounded front corners
  const r = Math.min(4, h * 0.1);
  return {
    tip: [t + l, h - r] as [number, number],
    nodes: [n(t, 0), n(t + l - r, 0, 0, 0, r * 0.55, 0), n(t + l, r, 0, -r * 0.55, 0, 0), n(t + l, h - r, 0, 0, 0, r * 0.55), n(t + l - r, h, r * 0.55, 0, 0, 0), n(t, h)],
  };
}

function kiritsuke(t: number, l: number, h: number) {
  // straight edge, straight angled front from the spine down to the tip (reverse tanto)
  const tip: [number, number] = [t + l, h * 0.92];
  return {
    tip,
    nodes: [n(t, 0), n(t + l * 0.72, 0), n(tip[0], tip[1]), n(t + l * 0.7, h, l * 0.18, 0, 0, 0), n(t, h)],
  };
}

/** Tang of a full-tang blade: a step down from the blade's spine, `tangW` tall, with its pin holes. */
function tang(t: number, h: number, tangW: number): { top: number; nodesBack: DocNode[]; nodesFront: DocNode[] } {
  const ty = Math.max(0, Math.min(h - tangW, h * 0.2));
  const step = Math.min(6, t / 2);
  return {
    top: ty,
    nodesFront: [n(0, ty), n(t - step, ty)],
    nodesBack: [n(t - step, ty + tangW), n(0, ty + tangW)],
  };
}

/** Grind line: plunge curving up from the edge near the ricasso, then running out at the tip.
 *  `percent` = grind height as a share of the blade height, measured from the edge. */
function grindLine(t: number, l: number, h: number, percent: number, tip: [number, number]): ShapePart[] {
  if (!(percent > 0)) return [];
  const gy = h * (1 - Math.min(95, percent) / 100);
  const plunge = Math.min(10, l * 0.1);
  return [
    {
      role: "grind",
      name: "Émouture",
      closed: false,
      contours: [[n(t + 3, h), n(t + 3 + plunge, gy, -plunge * 0.4, (h - gy) * 0.6), n(t + l * 0.62, gy), n(tip[0], tip[1], -l * 0.15, (gy - tip[1]) * 0.3)]],
    },
  ];
}

function dropPoint(p: Record<string, number>): ShapePart[] {
  const { blade: l, height: h, tang: t, tangW } = p;
  const tg = tang(t, h, Math.min(tangW, h));
  const tip: [number, number] = [t + l, h * 0.55];
  const outline = [
    ...tg.nodesFront,
    n(t, 0),
    n(t + l * 0.72, 0, 0, 0, l * 0.17, 0),
    n(tip[0], tip[1], -l * 0.08, -h * 0.38, -l * 0.05, h * 0.3),
    n(t + l * 0.55, h, l * 0.2, 0, 0, 0),
    n(t, h),
    ...tg.nodesBack,
  ];
  return [
    { role: "cut", name: "Lame", closed: true, contours: [dedupe(outline)] },
    ...grindLine(t, l, h, p.grind, tip),
    ...(t > 0 ? pinRow(p.pins, t, Math.min(t * 0.22, t / 2), tg.top + Math.min(tangW, h) / 2, p.pinD) : []),
  ];
}

function wharncliffe(p: Record<string, number>): ShapePart[] {
  const { blade: l, height: h, tang: t, tangW } = p;
  const tg = tang(t, h, Math.min(tangW, h));
  const tip: [number, number] = [t + l, h];
  const outline = [
    ...tg.nodesFront,
    n(t, 0),
    n(t + l * 0.35, 0, 0, 0, l * 0.35, 0),
    n(tip[0], tip[1], -l * 0.1, -h * 0.45, 0, 0), // the spine curves down onto a straight edge
    n(t, h),
    ...tg.nodesBack,
  ];
  return [
    { role: "cut", name: "Lame", closed: true, contours: [dedupe(outline)] },
    ...grindLine(t, l * 0.97, h, p.grind, [t + l * 0.97, h - 0.3]),
    ...(t > 0 ? pinRow(p.pins, t, Math.min(t * 0.22, t / 2), tg.top + Math.min(tangW, h) / 2, p.pinD) : []),
  ];
}

/** Drop consecutive nodes at the same place (a zero-length tang leaves some). */
function dedupe(nodes: DocNode[]): DocNode[] {
  const out: DocNode[] = [];
  for (const node of nodes) {
    const last = out[out.length - 1];
    if (last && Math.abs(last.x - node.x) < 1e-9 && Math.abs(last.y - node.y) < 1e-9) out[out.length - 1] = { ...last, ox: node.ox, oy: node.oy };
    else out.push(node);
  }
  return out;
}

/** Clamp the parameters to their bounds (whole numbers where needed); unknown keys get defaults. */
export function normalizeParams(def: ShapeDef, values: Record<string, unknown>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const param of def.params) {
    let v = Number(values[param.key]);
    if (!Number.isFinite(v)) v = param.value;
    v = Math.max(param.min, Math.min(param.max, v));
    out[param.key] = param.integer ? Math.round(v) : v;
  }
  return out;
}

/** Bounding box of the anchors (mm). */
export function partsBounds(parts: ShapePart[]): { minX: number; minY: number; maxX: number; maxY: number } | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const part of parts) {
    for (const c of part.contours) {
      for (const node of c) {
        minX = Math.min(minX, node.x);
        minY = Math.min(minY, node.y);
        maxX = Math.max(maxX, node.x);
        maxY = Math.max(maxY, node.y);
      }
    }
  }
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null;
}

/** Move parts so that their bounding box's top-left corner lands on (x, y). */
export function placeParts(parts: ShapePart[], x: number, y: number): ShapePart[] {
  const b = partsBounds(parts);
  if (!b) return parts;
  const dx = x - b.minX;
  const dy = y - b.minY;
  return parts.map((part) => ({ ...part, contours: part.contours.map((c) => c.map((node) => ({ ...node, x: round4(node.x + dx), y: round4(node.y + dy) }))) }));
}

const REUSABLE_ROLES: LayerRole[] = ["cut", "hole", "engrave", "grind"];

/** The drawn parts of another design (cut, holes, engraving, grind lines), to insert it as a shape. */
export function documentParts(doc: DesignDocument): ShapePart[] {
  const roles = new Map(doc.layers.map((l) => [l.id, l.role]));
  const out: ShapePart[] = [];
  for (const obj of doc.objects) {
    if (obj.type !== "path") continue;
    const role = roles.get(obj.layer);
    if (!role || !REUSABLE_ROLES.includes(role)) continue;
    out.push({ role, name: obj.name ?? "", closed: obj.closed, contours: obj.contours.map((c) => c.map((node) => ({ ...node }))) });
  }
  return out;
}
