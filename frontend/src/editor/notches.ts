/**
 * Jimping (thumb grip notches on the spine) and serrations (scallops on the edge): a row of
 * notches cut into a straight stretch of an outline, from point A to point B.
 *
 * Each notch is a closed shape straddling the edge line: it reaches `depth` into the material
 * and sticks out by `OUTSIDE_MM` on the empty side, so subtracting it from the outline leaves a
 * clean notch whatever the rounding. The engine subtracts the shapes from the selected part.
 *
 * - round: a circular arc of chord `width` and sagitta `depth`, radius R = (w²/4 + d²) / 2d.
 * - v: a V of opening `width` at the edge and point at `depth`.
 * - square: a flat-bottomed slot `width` wide.
 */

import { circleNodes } from "./drafting";
import type { DocNode } from "./types";

export type NotchShape = "round" | "v" | "square";

export interface NotchPattern {
  a: [number, number];
  b: [number, number];
  /** centre-to-centre distance */
  pitch: number;
  /** opening along the edge */
  width: number;
  /** how far into the material */
  depth: number;
  shape: NotchShape;
}

export const OUTSIDE_MM = 1;
export const MAX_NOTCHES = 400;

export const NOTCH_PRESETS = {
  // thumb jimping on the spine: small V grooves
  jimping: { pitch: 2, width: 1.2, depth: 0.6, shape: "v" as NotchShape },
  // classic serrated edge: shallow overlapping scallops
  serration: { pitch: 6, width: 5.5, depth: 1.6, shape: "round" as NotchShape },
};

const pt = (x: number, y: number): DocNode => ({ x, y, ix: 0, iy: 0, ox: 0, oy: 0 });

/** Centres of the notches along A→B, the row centred on the stretch. */
export function notchCentres(p: NotchPattern): [number, number][] {
  const dx = p.b[0] - p.a[0];
  const dy = p.b[1] - p.a[1];
  const len = Math.hypot(dx, dy);
  if (!(len > 0) || !(p.pitch > 0)) return [];
  const usable = len - p.width; // the first and last notch stay inside the stretch
  if (usable < 0) return [];
  const count = Math.min(MAX_NOTCHES, Math.floor(usable / p.pitch + 1e-9) + 1);
  const start = p.width / 2 + (usable - (count - 1) * p.pitch) / 2;
  return Array.from({ length: count }, (_, i) => {
    const s = (start + i * p.pitch) / len;
    return [p.a[0] + dx * s, p.a[1] + dy * s];
  });
}

/** Radius of the round notch: chord `width` at the edge, `depth` deep. */
export function roundNotchRadius(width: number, depth: number): number {
  return (width * width) / 4 / (2 * depth) + depth / 2;
}

/**
 * Notch outlines. `inward` is the unit normal pointing into the material at the edge
 * (the engine finds it by testing which side of A→B is inside the part).
 */
export function notchContours(p: NotchPattern, inward: [number, number]): DocNode[][] {
  if (!(p.width > 0) || !(p.depth > 0)) return [];
  const len = Math.hypot(p.b[0] - p.a[0], p.b[1] - p.a[1]);
  const u: [number, number] = [(p.b[0] - p.a[0]) / len, (p.b[1] - p.a[1]) / len];
  const [nx, ny] = inward;
  const at = (c: [number, number], along: number, into: number) => pt(c[0] + u[0] * along + nx * into, c[1] + u[1] * along + ny * into);

  return notchCentres(p).map((c) => {
    const half = p.width / 2;
    if (p.shape === "round") {
      const r = roundNotchRadius(p.width, p.depth);
      // circle centre on the inward normal, so the arc dips exactly `depth` below the edge
      const cx = c[0] + nx * (p.depth - r);
      const cy = c[1] + ny * (p.depth - r);
      return circleNodes(cx, cy, r);
    }
    if (p.shape === "v") {
      // the V's sides continue past the edge so the opening at the edge is exactly `width`
      const spread = half * (1 + OUTSIDE_MM / p.depth);
      return [at(c, -spread, -OUTSIDE_MM), at(c, spread, -OUTSIDE_MM), at(c, 0, p.depth)];
    }
    return [at(c, -half, -OUTSIDE_MM), at(c, half, -OUTSIDE_MM), at(c, half, p.depth), at(c, -half, p.depth)];
  });
}
