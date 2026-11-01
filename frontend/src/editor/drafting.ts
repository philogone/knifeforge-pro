/** Drafting constructions (fillet, chamfer, arcs, symmetry, hole patterns) as pure geometry on
 *  document nodes: millimetres, y down, Bézier handles relative to their anchor (see types.ts).
 *  Kept apart from Paper.js so every result can be checked against closed-form values. */

import type { DocNode } from "./types";

export type Vec = [number, number];

const EPS = 1e-9;
const round4 = (v: number) => Math.round(v * 10000) / 10000;
const sub = (a: Vec, b: Vec): Vec => [a[0] - b[0], a[1] - b[1]];
const add = (a: Vec, b: Vec): Vec => [a[0] + b[0], a[1] + b[1]];
const mul = (a: Vec, k: number): Vec => [a[0] * k, a[1] * k];
const len = (a: Vec) => Math.hypot(a[0], a[1]);
const unit = (a: Vec): Vec => mul(a, 1 / len(a));
const cross = (a: Vec, b: Vec) => a[0] * b[1] - a[1] * b[0];
const dot = (a: Vec, b: Vec) => a[0] * b[0] + a[1] * b[1];

function node(p: Vec, hin: Vec = [0, 0], hout: Vec = [0, 0]): DocNode {
  return { x: round4(p[0]), y: round4(p[1]), ix: round4(hin[0]), iy: round4(hin[1]), ox: round4(hout[0]), oy: round4(hout[1]) };
}

/**
 * Circular arc as Bézier nodes: centre, radius, start angle and signed sweep (radians, y down so a
 * positive sweep turns clockwise on screen). Split into pieces of at most 90°, each with the
 * standard handle length 4/3·tan(φ/4)·r, whose radial error is ≤ 2.7e-4·r (0.027 %).
 * The first node has no incoming handle and the last no outgoing one.
 */
export function arcNodes(center: Vec, r: number, start: number, sweep: number): DocNode[] {
  const pieces = Math.max(1, Math.ceil(Math.abs(sweep) / (Math.PI / 2) - 1e-9));
  const step = sweep / pieces;
  const k = (4 / 3) * Math.tan(step / 4) * r;
  const out: DocNode[] = [];
  for (let i = 0; i <= pieces; i++) {
    const a = start + step * i;
    const p: Vec = [center[0] + r * Math.cos(a), center[1] + r * Math.sin(a)];
    const tangent: Vec = [-Math.sin(a), Math.cos(a)]; // direction of increasing angle
    out.push(node(p, i > 0 ? mul(tangent, -k) : [0, 0], i < pieces ? mul(tangent, k) : [0, 0]));
  }
  return out;
}

export type CornerError = "notCorner" | "tooLarge" | "invalid";
export type CornerResult = { ok: true; nodes: DocNode[]; setback: number } | { ok: false; error: CornerError };

/**
 * Round a sharp corner `c` between straight edges coming from `prev` and going to `next`:
 * an arc of radius `r` tangent to both edges replaces the corner. The tangent points sit at
 * `setback` = r / tan(θ/2) from the corner (θ = angle between the edges), which must fit on both
 * edges (`maxPrev`, `maxNext` = usable length on each, defaulting to the whole edge).
 */
export function filletCorner(prev: Vec, c: Vec, next: Vec, r: number, maxPrev?: number, maxNext?: number): CornerResult {
  if (!(r > 0) || !Number.isFinite(r)) return { ok: false, error: "invalid" };
  const a = sub(prev, c);
  const b = sub(next, c);
  if (len(a) < EPS || len(b) < EPS) return { ok: false, error: "notCorner" };
  const ua = unit(a);
  const ub = unit(b);
  const theta = Math.acos(Math.max(-1, Math.min(1, dot(ua, ub))));
  if (theta < 1e-6 || Math.PI - theta < 1e-6) return { ok: false, error: "notCorner" }; // collinear: nothing to round
  const setback = r / Math.tan(theta / 2);
  if (setback > (maxPrev ?? len(a)) + 1e-9 || setback > (maxNext ?? len(b)) + 1e-9) return { ok: false, error: "tooLarge" };
  const t1 = add(c, mul(ua, setback));
  const t2 = add(c, mul(ub, setback));
  const bisector = unit(add(ua, ub));
  const center = add(c, mul(bisector, r / Math.sin(theta / 2)));
  const start = Math.atan2(t1[1] - center[1], t1[0] - center[0]);
  // sweep from t1 to t2 the short way round (the fillet's arc is always under 180°)
  let sweep = Math.atan2(t2[1] - center[1], t2[0] - center[0]) - start;
  while (sweep > Math.PI) sweep -= 2 * Math.PI;
  while (sweep < -Math.PI) sweep += 2 * Math.PI;
  const nodes = arcNodes(center, r, start, sweep);
  // pin the ends exactly on the tangent points (no trigonometric round-off on the edges)
  nodes[0] = { ...nodes[0], x: round4(t1[0]), y: round4(t1[1]) };
  nodes[nodes.length - 1] = { ...nodes[nodes.length - 1], x: round4(t2[0]), y: round4(t2[1]) };
  return { ok: true, nodes, setback };
}

/** Cut a sharp corner with a straight chamfer `d` long on each edge (symmetric chamfer). */
export function chamferCorner(prev: Vec, c: Vec, next: Vec, d: number, maxPrev?: number, maxNext?: number): CornerResult {
  if (!(d > 0) || !Number.isFinite(d)) return { ok: false, error: "invalid" };
  const a = sub(prev, c);
  const b = sub(next, c);
  if (len(a) < EPS || len(b) < EPS || Math.abs(cross(unit(a), unit(b))) < 1e-9) return { ok: false, error: "notCorner" };
  if (d > (maxPrev ?? len(a)) + 1e-9 || d > (maxNext ?? len(b)) + 1e-9) return { ok: false, error: "tooLarge" };
  return { ok: true, nodes: [node(add(c, mul(unit(a), d))), node(add(c, mul(unit(b), d)))], setback: d };
}

/** Centre of the circle through three points, or null when they are (nearly) aligned. */
export function circleThrough(a: Vec, b: Vec, c: Vec): { center: Vec; r: number } | null {
  const d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]));
  const scale = Math.max(len(sub(b, a)), len(sub(c, a)), 1);
  if (Math.abs(d) < 1e-9 * scale * scale) return null;
  const a2 = dot(a, a);
  const b2 = dot(b, b);
  const c2 = dot(c, c);
  const center: Vec = [(a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d, (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d];
  return { center, r: len(sub(a, center)) };
}

/** Arc from `start` to `end` passing through `through`; a straight segment when the points are aligned. */
export function arcThrough(start: Vec, through: Vec, end: Vec): DocNode[] {
  const circle = circleThrough(start, through, end);
  if (!circle) return [node(start), node(end)];
  const { center, r } = circle;
  const ang = (p: Vec) => Math.atan2(p[1] - center[1], p[0] - center[0]);
  const a0 = ang(start);
  const norm = (x: number) => ((x % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  // go the way that passes through `through`
  const toThrough = norm(ang(through) - a0);
  const toEnd = norm(ang(end) - a0);
  const sweep = toThrough <= toEnd ? toEnd : toEnd - 2 * Math.PI;
  const nodes = arcNodes(center, r, a0, sweep);
  nodes[0] = { ...nodes[0], x: round4(start[0]), y: round4(start[1]) };
  nodes[nodes.length - 1] = { ...nodes[nodes.length - 1], x: round4(end[0]), y: round4(end[1]) };
  return nodes;
}

// ---------------------------------------------------------------- symmetry
export interface Axis {
  /** "x": vertical axis x = pos; "y": horizontal axis y = pos */
  axis: "x" | "y";
  pos: number;
}

const neg = (v: number) => (v === 0 ? 0 : -v); // no "-0" in documents

export function mirrorNode(n: DocNode, ax: Axis): DocNode {
  return ax.axis === "x"
    ? { x: round4(2 * ax.pos - n.x), y: n.y, ix: neg(n.ix), iy: n.iy, ox: neg(n.ox), oy: n.oy }
    : { x: n.x, y: round4(2 * ax.pos - n.y), ix: n.ix, iy: neg(n.iy), ox: n.ox, oy: neg(n.oy) };
}

/**
 * Complete a half outline drawn on one side of an axis. When both ends lie on the axis (within
 * `tolerance`), the half and its mirror image are joined into one closed contour, the ends pinned
 * exactly on the axis. Otherwise the mirror is returned as a separate open path.
 */
export function symmetricComplete(half: DocNode[], ax: Axis, tolerance: number): { closed: DocNode[] } | { mirror: DocNode[] } {
  const onAxis = (n: DocNode) => Math.abs((ax.axis === "x" ? n.x : n.y) - ax.pos) <= tolerance;
  const first = half[0];
  const last = half[half.length - 1];
  if (half.length >= 2 && onAxis(first) && onAxis(last)) {
    const pin = (n: DocNode): DocNode => (ax.axis === "x" ? { ...n, x: round4(ax.pos) } : { ...n, y: round4(ax.pos) });
    const a = { ...pin(first) };
    const b = { ...pin(last) };
    const middle = half.slice(1, -1);
    // mirrored half, walked back from `last` to `first`: reversing a path swaps in/out handles
    const back = [...middle].reverse().map((n) => {
      const m = mirrorNode(n, ax);
      return { ...m, ix: m.ox, iy: m.oy, ox: m.ix, oy: m.iy };
    });
    const mb = mirrorNode(b, ax);
    const ma = mirrorNode(a, ax);
    // the joints keep the drawn handle on one side and its mirror on the other
    const joinB: DocNode = { ...b, ox: mb.ix, oy: mb.iy };
    const joinA: DocNode = { ...a, ix: ma.ox, iy: ma.oy };
    return { closed: [joinA, ...middle, joinB, ...back] };
  }
  return { mirror: half.map((n) => mirrorNode(n, ax)) };
}

// ------------------------------------------------------------ hole patterns
/** Common pin / rivet / screw diameters (mm), metric and imperial. */
export const STANDARD_HOLES_MM: { d: number; label: string }[] = [
  { d: 1.5, label: "1,5" },
  { d: 2, label: "2" },
  { d: 2.38, label: "2,38 (3/32″)" },
  { d: 2.5, label: "2,5" },
  { d: 3, label: "3" },
  { d: 3.18, label: "3,18 (1/8″)" },
  { d: 4, label: "4" },
  { d: 4.76, label: "4,76 (3/16″)" },
  { d: 5, label: "5" },
  { d: 6, label: "6" },
  { d: 6.35, label: "6,35 (1/4″)" },
  { d: 8, label: "8" },
];

/** 4-node Bézier circle, the editor's standard (radial error ≤ 0.027 % of r). */
export function circleNodes(cx: number, cy: number, r: number): DocNode[] {
  const k = (4 / 3) * Math.tan(Math.PI / 8) * r;
  return [
    node([cx + r, cy], [0, -k], [0, k]),
    node([cx, cy + r], [k, 0], [-k, 0]),
    node([cx - r, cy], [0, k], [0, -k]),
    node([cx, cy - r], [-k, 0], [k, 0]),
  ];
}

export interface HolePattern {
  x: number;
  y: number;
  diameter: number;
  count: number;
  /** distance between consecutive hole centres */
  pitch: number;
  /** direction of the row, degrees, measured like the measure tool (counter-clockwise, y up) */
  angle: number;
}

/** Centres of a row of holes, first one at (x, y). */
export function holeCentres(p: HolePattern): Vec[] {
  const n = Math.max(1, Math.min(200, Math.round(p.count)));
  const rad = (p.angle * Math.PI) / 180;
  const dir: Vec = [Math.cos(rad), -Math.sin(rad)]; // y down on screen, y up for the user
  return Array.from({ length: n }, (_, i) => [round4(p.x + dir[0] * p.pitch * i), round4(p.y + dir[1] * p.pitch * i)] as Vec);
}
