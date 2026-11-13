/**
 * Folding knives: distance between outlines, used to check the blade's swing around its pivot.
 * The engine rotates the blade (paper.js) and asks these helpers how close it comes to each
 * obstacle (stop pin, backspring, lock bar) once flattened to polylines.
 */

export type Polyline = [number, number][];

function pointSegmentDistance([px, py]: [number, number], [ax, ay]: [number, number], [bx, by]: [number, number]): number {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0;
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

/** Smallest distance between two closed outlines that do not overlap (vertex to segment, both ways). */
export function outlineDistance(a: Polyline, b: Polyline): number {
  let best = Infinity;
  const pass = (from: Polyline, to: Polyline) => {
    for (const p of from) {
      for (let i = 0; i < to.length; i++) {
        const d = pointSegmentDistance(p, to[i], to[(i + 1) % to.length]);
        if (d < best) best = d;
      }
    }
  };
  pass(a, b);
  pass(b, a);
  return best;
}

/** Angles from 0 to `to` (either sign) every `step` degrees, `to` itself included. */
export function sweepAngles(to: number, step = 0.5): number[] {
  const n = Math.max(1, Math.ceil(Math.abs(to) / step));
  return Array.from({ length: n + 1 }, (_, i) => (i === 0 ? 0 : (to * i) / n));
}
