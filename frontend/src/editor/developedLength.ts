/**
 * Developed length: how much bar to cut to forge or bend the drawn shape (a scroll, a hook, a
 * ring, a twist of the leaf), and the bar length that holds a forged part's volume.
 *
 * The bar is bent about its neutral fibre, which keeps its length. The drawn line may be the
 * bar's centre line, or one of its edges; the neutral fibre then lies at `k × t` from the inside
 * edge (t: the bar's dimension across the bend, k: neutral fibre coefficient, 0.5 for a hot or
 * gentle bend, down to about 0.33 for tight cold bends).
 *
 * Exact offset length: a smooth curve of length L offset by δ away from the side it turns to
 * has length L + δ·|Θ|, Θ being the total angle it turns through (radians), as long as it
 * turns one way. So the neutral-fibre length needs only the drawn length and its total turning.
 * For an S-shape (bends both ways), draw the centre line.
 */

export type Point = [number, number];
export type Section =
  | { kind: "round"; d: number }
  | { kind: "square"; a: number }
  | { kind: "flat"; w: number; t: number; onEdge: boolean }; // on edge: bent across its width

export type Reference = "centre" | "inside" | "outside";

/** Length and signed total turning angle (radians) of a polyline. */
export function lengthAndTurning(points: Point[], closed: boolean): { length: number; turning: number } {
  const pts = closed ? [...points, points[0]] : points;
  let length = 0;
  let turning = 0;
  let prev: Point | null = null;
  for (let i = 1; i < pts.length; i++) {
    const d: Point = [pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]];
    const len = Math.hypot(d[0], d[1]);
    if (len < 1e-12) continue;
    length += len;
    if (prev) turning += Math.atan2(prev[0] * d[1] - prev[1] * d[0], prev[0] * d[0] + prev[1] * d[1]);
    prev = d;
  }
  if (closed && prev && pts.length > 2) {
    // the turn at the start point, to close the loop
    const first: Point = [pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]];
    turning += Math.atan2(prev[0] * first[1] - prev[1] * first[0], prev[0] * first[0] + prev[1] * first[1]);
  }
  return { length, turning };
}

/** The bar's dimension across the bend (the one that is bent). */
export function bendDepth(s: Section): number {
  if (s.kind === "round") return s.d;
  if (s.kind === "square") return s.a;
  return s.onEdge ? s.w : s.t;
}

export function sectionArea(s: Section): number {
  if (s.kind === "round") return (Math.PI * s.d * s.d) / 4;
  if (s.kind === "square") return s.a * s.a;
  return s.w * s.t;
}

export interface DevelopedLength {
  drawn: number;
  /** total turning of the drawn line, degrees (absolute) */
  turningDeg: number;
  neutral: number;
  allowances: number;
  cut: number;
  weightG: number;
}

/**
 * `points`: the drawn line (flattened), `reference`: what the line is, `k`: neutral fibre
 * coefficient, `extra`: allowances to add (mm: grip, trimming), `lossPct`: forging loss (scale).
 */
export function developedLength(
  points: Point[],
  closed: boolean,
  section: Section,
  reference: Reference,
  k = 0.5,
  extra = 0,
  lossPct = 0,
  density = 7.85,
): DevelopedLength {
  const { length, turning } = lengthAndTurning(points, closed);
  const t = bendDepth(section);
  // the drawn line sits p from the bar's inside edge, the neutral fibre k·t from it: going
  // outwards by δ lengthens the line by δ·|Θ| (bends all the same way: scroll, ring, hook)
  const p = reference === "inside" ? 0 : reference === "centre" ? t / 2 : t;
  const neutral = length + (k * t - p) * Math.abs(turning);
  const allowances = extra + (neutral * lossPct) / 100;
  const cut = neutral + allowances;
  return { drawn: length, turningDeg: (Math.abs(turning) * 180) / Math.PI, neutral, allowances, cut, weightG: (sectionArea(section) * cut * density) / 1000 };
}

/** Bar length of a given section holding a part's volume (forging to shape), losses added. */
export function forgingStock(partVolumeMm3: number, section: Section, lossPct = 0): number {
  const a = sectionArea(section);
  return a > 0 ? (partVolumeMm3 / a) * (1 + lossPct / 100) : 0;
}
