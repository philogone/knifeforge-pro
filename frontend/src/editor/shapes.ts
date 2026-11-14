/** Parametric shape library: knifemaking parts built from exact Bézier nodes (mm, y down),
 *  each drawn from (0, 0) at its top-left, then inserted where the user wants it.
 *  Also turns another design into a reusable shape ("my templates"). */

import { defaultLayers } from "./constants";
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

/** Families the library lists the shapes under. */
export type ShapeGroup = "parts" | "fixed" | "kitchen" | "folder";
export const SHAPE_GROUPS: ShapeGroup[] = ["parts", "fixed", "kitchen", "folder"];

export interface ShapeDef {
  key: string;
  /** i18n key */
  label: string;
  group: ShapeGroup;
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
    group: "parts",
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
    group: "parts",
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
    group: "parts",
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
    group: "parts",
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
    group: "parts",
    params: [
      { key: "length", label: "shape.p.slotL", value: 18, min: 1, max: 200 },
      { key: "width", label: "shape.p.slotW", value: 4.5, min: 0.5, max: 50 },
    ],
    build: (p) => [{ role: "hole", name: "Fente de soie", closed: true, contours: [slot(Math.max(p.length, p.width) / 2, p.width / 2, p.length, p.width)] }],
  },
  bladeShape("dropPoint", 112, 32, 105, 24, 2, 5, 50, dropPointBlade),
  bladeShape("wharncliffe", 90, 25, 95, 21, 2, 4, 45, wharncliffe),
  bladeShape("clipPoint", 100, 30, 100, 23, 2, 4.76, 50, clipPoint),
  bladeShape("spearPoint", 95, 26, 95, 22, 2, 4.76, 50, spearPoint),
  bladeShape("tanto", 110, 30, 105, 24, 2, 5, 55, tanto),
  bladeShape("sheepsfoot", 85, 24, 95, 21, 2, 4, 45, sheepsfoot),
  bladeShape("trailingPoint", 105, 30, 105, 24, 2, 5, 50, trailingPoint),
  bladeShape("skinner", 85, 34, 100, 25, 3, 4.76, 55, skinner),
  bladeShape("bowie", 200, 40, 125, 28, 3, 6.35, 50, bowie),
  bladeShape("paring", 85, 20, 95, 18, 2, 3.18, 60, paring, "kitchen"),
  bladeShape("gyuto", 210, 48, 125, 24, 3, 4.76, 70, gyuto, "kitchen"),
  bladeShape("santoku", 170, 46, 120, 24, 3, 4.76, 70, santoku, "kitchen"),
  bladeShape("nakiri", 165, 50, 120, 24, 3, 4.76, 70, nakiri, "kitchen"),
  bladeShape("kiritsuke", 240, 46, 130, 24, 3, 4.76, 70, kiritsuke, "kitchen"),
  bladeShape("folderDropPoint", 85, 20, 24, 0, 1, 4, 55, dropPointBlade, "folder"),
  bladeShape("yatagan", 105, 20, 26, 0, 1, 4, 55, yatagan, "folder"),
  bladeShape("sageLeaf", 90, 22, 26, 0, 1, 4, 55, sageLeaf, "folder"),
  bladeShape("london", 80, 22, 24, 0, 1, 4, 55, london, "folder"),
  bladeShape("yssingeaux", 90, 18, 24, 0, 1, 4, 55, yssingeaux, "folder"),
  bladeShape("saintAmand", 85, 16, 22, 0, 1, 3.5, 55, willowLeaf, "folder"),
  bladeShape("vendetta", 110, 18, 24, 0, 1, 4, 55, vendetta, "folder"),
];

/**
 * How the blade ends at the back:
 * - hunter: full tang shaped as the handle, sharpening choil and a finger guard;
 * - kitchen: full tang, sharp heel dropping to the handle (chef's knives);
 * - folder: rounded tang round the pivot hole, with a sharpening choil (no handle).
 */
type Heel = "hunter" | "kitchen" | "folder";
type Outline = (t: number, l: number, h: number) => { nodes: DocNode[]; tip: [number, number] };

/**
 * A blade profile: `outline` gives the nodes from the spine at the blade's start (t, 0), round
 * the tip, back to the edge at (t, h); the heel (handle, finger guard or pivot tang) and the
 * holes are added around it.
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
  outline: Outline,
  heel: Heel = "hunter",
): ShapeDef {
  const common = [
    { key: "blade", label: "shape.p.bladeLength", value: blade, min: 30, max: 400 },
    { key: "height", label: "shape.p.bladeHeight", value: height, min: 10, max: 120 },
  ];
  const grindParam = { key: "grind", label: "shape.p.grindHeight", value: grind, min: 0, max: 100, percent: true };
  const params: ShapeParam[] =
    heel === "folder"
      ? [
          ...common,
          { key: "tang", label: "shape.p.talonLength", value: tangLength, min: 0, max: 120 },
          { key: "pinD", label: "shape.p.pivotD", value: pinD, min: 0, max: 20 },
          grindParam,
        ]
      : [
          ...common,
          { key: "tang", label: "shape.p.handleLength", value: tangLength, min: 0, max: 300 },
          { key: "tangW", label: "shape.p.handleHeight", value: tangW, min: 3, max: 100 },
          { key: "pins", label: "shape.p.pins", value: pins, min: 0, max: 6, integer: true },
          { key: "pinD", label: "shape.p.pinD", value: pinD, min: 0.5, max: 20 },
          grindParam,
        ];
  return {
    key,
    label: `shape.${key}`,
    group: heel === "hunter" ? "fixed" : heel,
    params,
    build: (p) => {
      const { blade: l, height: h, tang: t } = p;
      const { nodes, tip } = outline(t, l, h);
      const end = heelNodes(heel, nodes, t, h, Math.min(p.tangW ?? h, h));
      const grindTip: [number, number] = [tip[0] - Math.min(2, l * 0.02), Math.min(tip[1], h)];
      return [
        { role: "cut", name: "Lame", closed: true, contours: [dedupe(end.contour)] },
        ...grindLine(end.grindStart, grindTip[0] - end.grindStart, h, p.grind, grindTip),
        ...end.holes(p),
      ];
    },
  };
}

const K = 0.5523; // quarter circle handle factor, 4/3·tan(π/8)

/** Close the outline with its heel (handle, finger guard or pivot tang) and place the holes. */
function heelNodes(heel: Heel, outline: DocNode[], t: number, h: number, H: number) {
  const body = outline.slice(0, -1);
  const last = outline[outline.length - 1];
  const rc = Math.max(1, Math.min(3, h * 0.08)); // sharpening choil radius
  // too short for a handle or a tang: a straight back
  if (heel === "folder" ? t < h * 0.3 : t < 12) return { contour: outline, grindStart: t + 3, holes: () => [] as ShapePart[] };

  if (heel === "kitchen") {
    // sharp heel, concave fillet up to the handle, gentle palm swell, rounded butt
    const step = h - H;
    const fr = Math.max(0.5, Math.min(step * 0.9, 10, t * 0.15));
    const back = [
      n(t, h, last.ix, last.iy, 0, -Math.max(0, step - fr) * 0.4),
      ...(step > 0.5 ? [n(t - fr, H, fr * 0.6, 0, -t * 0.2, 0)] : []),
      n(t * 0.42, H * 1.04, t * 0.2, 0, -t * 0.22, 0),
      n(t * 0.05, H * 0.97, t * 0.12, 0, -t * 0.035, 0),
      n(0, H * 0.5, 0, H * 0.3, 0, -H * 0.3),
      n(t * 0.05, H * 0.03, -t * 0.035, 0, t * 0.25, 0),
    ];
    return { contour: [...body, ...back], grindStart: t + 3, holes: (p: Record<string, number>) => pinsAlong(p.pins, t * 0.16, t * 0.8, H / 2, p.pinD) };
  }

  if (heel === "hunter") {
    // choil, finger guard, index groove, palm swell, slightly flared butt
    const gb = rc * 0.9;
    const step = h - H;
    const gd = Math.min(2, step * 0.22);
    const gw = Math.min(t * 0.22, step * 1.2 + 7);
    const sw = H * 0.07;
    const edgeStart = t + gb + 2 * rc;
    const back = [
      n(edgeStart, h, last.ix, last.iy, 0, -rc * K),
      n(t + gb + rc, h - rc, rc * K, 0, -rc * K, 0),
      n(t + gb, h, 0, -rc * K, 0, rc * 0.5),
      n(t - gb * 0.4, h + gd, gb * 0.8, 0, -gb * 0.9 - step * 0.2, 0),
      n(t - gw, H - Math.min(1.5, H * 0.05), gw * 0.5, 0, -t * 0.16, 0),
      n(t * 0.36, H + sw, t * 0.18, 0, -t * 0.2, 0),
      n(t * 0.06, H + sw * 0.4, t * 0.12, 0, -t * 0.04, 0),
      n(0, H * 0.52, 0, H * 0.32, 0, -H * 0.3),
      n(t * 0.06, H * 0.04, -t * 0.04, 0, t * 0.25, 0),
    ];
    return {
      contour: [...body, ...back],
      grindStart: edgeStart + 1,
      holes: (p: Record<string, number>) => pinsAlong(p.pins, t * 0.2, t - gw - (p.pinD || 0), H / 2, p.pinD),
    };
  }

  // folder: choil, flat kick under the pivot, round tang about the pivot hole
  const R = h / 2;
  const cx = Math.max(R * 0.6, t - Math.min(t * 0.45, R * 0.9));
  const edgeStart = t + 2 * rc;
  const back = [
    n(edgeStart, h, last.ix, last.iy, 0, -rc * K),
    n(t + rc, h - rc, rc * K, 0, -rc * K, 0),
    n(t, h, 0, -rc * K, 0, 0),
    n(cx, h, 0, 0, -R * K, 0),
    n(cx - R, R, 0, R * K, 0, -R * K),
    n(cx, 0, -R * K, 0, 0, 0),
  ];
  return {
    contour: [...body, ...back],
    grindStart: edgeStart + 1,
    holes: (p: Record<string, number>) => (p.pinD > 0 && p.pinD < h * 0.8 ? [hole(cx, R, p.pinD, "Pivot")] : []),
  };
}

/** `count` holes evenly spread from x0 to x1 on y = cy. */
function pinsAlong(count: number, x0: number, x1: number, cy: number, d: number): ShapePart[] {
  const c = Math.max(0, Math.round(count));
  if (!c || !(d > 0) || x1 <= x0) return [];
  if (c === 1) return [hole((x0 + x1) / 2, cy, d, "Perçage 1")];
  const step = (x1 - x0) / (c - 1);
  return Array.from({ length: c }, (_, i) => hole(x0 + step * i, cy, d, `Perçage ${i + 1}`));
}

// Each outline runs spine → tip → edge, y down (spine at 0, edge at h). Handles are relative.
// The tip is a true point: the spine comes in at `a` degrees below the horizontal, the edge
// leaves backwards at `b` degrees below the horizontal.
const rad = (deg: number) => (deg * Math.PI) / 180;
function tipNode(x: number, y: number, a: number, la: number, b: number, lb: number): DocNode {
  return n(x, y, -Math.cos(rad(a)) * la, -Math.sin(rad(a)) * la, -Math.cos(rad(b)) * lb, Math.sin(rad(b)) * lb);
}

function dropPointBlade(t: number, l: number, h: number) {
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.4];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.56), 0, 0, 0, l * 0.2, 0), tipNode(tip[0], tip[1], 26, l * 0.12, 36, h * 0.55), n(F(0.5), h, l * 0.24, 0, 0, 0), n(t, h)],
  };
}

function paring(t: number, l: number, h: number) {
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.58];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.45), 0, 0, 0, l * 0.28, 0), tipNode(tip[0], tip[1], 30, l * 0.12, 18, l * 0.14), n(F(0.6), h, l * 0.18, 0, 0, 0), n(t, h)],
  };
}

function clipPoint(t: number, l: number, h: number) {
  // straight spine, then a hollow clip down to a tip a third of the way down
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.3];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.6), 0, 0, 0, l * 0.12, h * 0.16), tipNode(tip[0], tip[1], 6, l * 0.14, 46, h * 0.62), n(F(0.52), h, l * 0.24, 0, 0, 0), n(t, h)],
  };
}

function spearPoint(t: number, l: number, h: number) {
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.5];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.5), 0, 0, 0, l * 0.26, 0), tipNode(tip[0], tip[1], 24, l * 0.13, 24, l * 0.13), n(F(0.5), h, l * 0.26, 0, 0, 0), n(t, h)],
  };
}

function tanto(t: number, l: number, h: number) {
  // straight edge to a secondary point, then a straight front edge up to the tip
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.14];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.7), 0), n(tip[0], tip[1]), n(F(0.85), h), n(t, h)],
  };
}

function sheepsfoot(t: number, l: number, h: number) {
  // straight edge, the spine rolls down to meet it
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.5), 0, 0, 0, l * 0.3, 0), n(tip[0], tip[1], -Math.cos(rad(72)) * h * 0.6, -Math.sin(rad(72)) * h * 0.6, 0, 0), n(t, h)],
  };
}

function wharncliffe(t: number, l: number, h: number) {
  // straight edge, the spine tapers down in one long curve onto it
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.28), 0, 0, 0, l * 0.32, 0), n(tip[0], tip[1], -Math.cos(rad(30)) * l * 0.28, -Math.sin(rad(30)) * l * 0.28, 0, 0), n(t, h)],
  };
}

function trailingPoint(t: number, l: number, h: number) {
  // the tip rises above the spine line, long sweeping belly
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), -h * 0.16];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.42), h * 0.03, -l * 0.15, 0, l * 0.25, 0), tipNode(tip[0], tip[1], -14, l * 0.18, 52, h * 0.75), n(F(0.42), h, l * 0.32, 0, 0, 0), n(t, h)],
  };
}

function skinner(t: number, l: number, h: number) {
  // broad belly for long sweeping cuts, tip well below the spine
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.32];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.38), 0, 0, 0, l * 0.28, 0), tipNode(tip[0], tip[1], 24, l * 0.14, 58, h * 0.7), n(F(0.36), h, l * 0.34, 0, 0, 0), n(t, h)],
  };
}

function bowie(t: number, l: number, h: number) {
  // long hollow clip starting past the middle, generous belly
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.3];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.56), 0, 0, 0, l * 0.12, h * 0.16), tipNode(tip[0], tip[1], 5, l * 0.16, 40, h * 0.7), n(F(0.55), h, l * 0.24, 0, 0, 0), n(t, h)],
  };
}

function gyuto(t: number, l: number, h: number) {
  // chef's knife: flat heel, long curve rising to a tip high on the blade
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.26];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.5), 0, 0, 0, l * 0.3, 0), tipNode(tip[0], tip[1], 12, l * 0.14, 22, l * 0.22), n(F(0.42), h, l * 0.3, 0, 0, 0), n(t, h)],
  };
}

function santoku(t: number, l: number, h: number) {
  // sheepsfoot-like nose dropping to a tip just above the edge, nearly flat edge
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.88];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.52), 0, 0, 0, l * 0.3, 0), tipNode(tip[0], tip[1], 62, h * 0.5, 10, l * 0.12), n(F(0.6), h, l * 0.18, 0, 0, 0), n(t, h)],
  };
}

function nakiri(t: number, l: number, h: number) {
  // rectangular vegetable cleaver, rounded front corners, a hint of curve at the front
  const r = Math.min(6, h * 0.12);
  const F = (f: number) => t + l * f;
  return {
    tip: [F(1), h - r] as [number, number],
    nodes: [n(t, 0), n(F(1) - r, 0, 0, 0, r * K, 0), n(F(1), r, 0, -r * K, l * 0.004, h * 0.3), n(F(1), h - r, 0, -h * 0.3, 0, r * K), n(F(1) - r, h, r * K, 0, 0, 0), n(t, h)],
  };
}

function kiritsuke(t: number, l: number, h: number) {
  // straight edge, straight angled front from the spine down to the tip (reverse tanto)
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.9];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.74), 0), n(tip[0], tip[1], 0, 0, -Math.cos(rad(8)) * l * 0.12, Math.sin(rad(8)) * l * 0.12), n(F(0.65), h, l * 0.15, 0, 0, 0), n(t, h)],
  };
}

function yatagan(t: number, l: number, h: number) {
  // yatagan (Aubrac, Basque country…): the spine drops in a light hollow to a raised tip; the edge is straight at the heel,
  // hollow just after it and full towards the tip
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.24];
  return {
    tip,
    nodes: [
      n(t, 0),
      n(F(0.62), h * 0.02, -l * 0.2, 0, l * 0.12, h * 0.05),
      tipNode(tip[0], tip[1], 8, l * 0.14, 40, h * 0.6),
      n(F(0.6), h, l * 0.18, 0, -l * 0.14, 0),
      n(F(0.3), h * 0.94, l * 0.1, 0, -l * 0.1, 0),
      n(F(0.08), h, l * 0.08, 0, 0, 0),
      n(t, h),
    ],
  };
}

function sageLeaf(t: number, l: number, h: number) {
  // feuille de sauge (Nontron): a leaf, the spine swells then curves down to a central point
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.5];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.4), -h * 0.06, -l * 0.2, 0, l * 0.24, 0), tipNode(tip[0], tip[1], 30, l * 0.14, 30, l * 0.14), n(F(0.45), h, l * 0.26, 0, 0, 0), n(t, h)],
  };
}

function london(t: number, l: number, h: number) {
  // London (French folder): straight edge, the spine runs straight then rolls down in one long
  // curve to a point on the edge line
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.4), 0, 0, 0, l * 0.34, 0), n(tip[0], tip[1], -Math.cos(rad(50)) * h * 0.85, -Math.sin(rad(50)) * h * 0.85, 0, 0), n(t, h)],
  };
}

function yssingeaux(t: number, l: number, h: number) {
  // Yssingeaux (French folder): slender blade, straight spine dropping late to a tip near the
  // middle, light belly
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.46];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.62), 0, 0, 0, l * 0.18, 0), tipNode(tip[0], tip[1], 28, l * 0.1, 30, l * 0.12), n(F(0.6), h, l * 0.18, 0, 0, 0), n(t, h)],
  };
}

function willowLeaf(t: number, l: number, h: number) {
  // feuille de saule (Saint-Amand, Aquitaine): a slender leaf, spine and edge curving evenly
  // to a central point
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.5];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.42), -h * 0.04, -l * 0.18, 0, l * 0.28, 0), tipNode(tip[0], tip[1], 20, l * 0.16, 20, l * 0.16), n(F(0.48), h, l * 0.28, 0, 0, 0), n(t, h)],
  };
}

function vendetta(t: number, l: number, h: number) {
  // vendetta (Corsica): long narrow stiletto blade, straight spine and edge tapering to a
  // sharp point a little above the middle
  const F = (f: number) => t + l * f;
  const tip: [number, number] = [F(1), h * 0.42];
  return {
    tip,
    nodes: [n(t, 0), n(F(0.5), 0, 0, 0, l * 0.2, 0), tipNode(tip[0], tip[1], 10, l * 0.2, 14, l * 0.22), n(F(0.45), h, l * 0.22, 0, 0, 0), n(t, h)],
  };
}

/** Grind line: plunge curving up from the edge near the heel, then running out at the tip.
 *  `percent` = grind height as a share of the blade height, measured from the edge. */
function grindLine(x0: number, l: number, h: number, percent: number, tip: [number, number]): ShapePart[] {
  if (!(percent > 0) || !(l > 0)) return [];
  const gy = h * (1 - Math.min(95, percent) / 100);
  const plunge = Math.min(10, l * 0.1);
  return [
    {
      role: "grind",
      name: "Émouture",
      closed: false,
      contours: [[n(x0, h), n(x0 + plunge, gy, -plunge * 0.4, (h - gy) * 0.6), n(x0 + l * 0.62, gy), n(tip[0], tip[1], -l * 0.15, (gy - tip[1]) * 0.3)]],
    },
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

/** A library shape at its default parameters, as a new design's document (top-left at 0, 0). */
export function shapeDocument(def: ShapeDef): DesignDocument {
  const layers = defaultLayers();
  const layerOf = (role: LayerRole) => layers.find((l) => l.role === role)!.id;
  const parts = placeParts(def.build(normalizeParams(def, {})), 0, 0);
  return {
    version: 1,
    unit: "mm",
    layers,
    objects: parts.map((p, i) => ({ id: `${def.key}-${i + 1}`, type: "path" as const, layer: layerOf(p.role), name: p.name || null, closed: p.closed, contours: p.contours })),
  };
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
