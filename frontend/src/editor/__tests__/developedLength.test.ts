import { describe, expect, it } from "vitest";

import { developedLength, forgingStock, lengthAndTurning, sectionArea, type Point } from "../developedLength";

const arc = (r: number, from: number, to: number, n = 2000): Point[] =>
  Array.from({ length: n + 1 }, (_, i) => {
    const a = from + ((to - from) * i) / n;
    return [r * Math.cos(a), r * Math.sin(a)];
  });

describe("developed length", () => {
  it("measures a circle and its full turn", () => {
    const ring = arc(50, 0, 2 * Math.PI, 4000).slice(0, -1);
    const { length, turning } = lengthAndTurning(ring, true);
    expect(length).toBeCloseTo(2 * Math.PI * 50, 2);
    expect(Math.abs(turning)).toBeCloseTo(2 * Math.PI, 6);
  });

  it("puts the neutral fibre where the reference says, for a ring of 10 mm round bar", () => {
    // ring drawn by its inside edge, Ø 100 inside: neutral at Ø 110 (k = 0.5)
    const inside = arc(50, 0, 2 * Math.PI, 4000).slice(0, -1);
    const r = developedLength(inside, true, { kind: "round", d: 10 }, "inside");
    expect(r.neutral).toBeCloseTo(Math.PI * 110, 1);
    // the same ring drawn by its outside edge (Ø 120)
    const outside = arc(60, 0, 2 * Math.PI, 4000).slice(0, -1);
    expect(developedLength(outside, true, { kind: "round", d: 10 }, "outside").neutral).toBeCloseTo(Math.PI * 110, 1);
    // tight cold bend, k = 0.4: the fibre moves 1 mm inwards from the centre line
    expect(developedLength(inside, true, { kind: "round", d: 10 }, "inside", 0.4).neutral).toBeCloseTo(Math.PI * 108, 1);
  });

  it("matches an Archimedean spiral (a scroll) within a hundredth", () => {
    // r = a + bθ over two turns, drawn as the centre line: exact length by integration
    const a = 10, b = 4, turns = 2 * 2 * Math.PI;
    const pts: Point[] = Array.from({ length: 20001 }, (_, i) => {
      const th = (turns * i) / 20000;
      const r = a + b * th;
      return [r * Math.cos(th), r * Math.sin(th)];
    });
    let exact = 0;
    const n = 200000;
    for (let i = 0; i < n; i++) {
      const th = (turns * (i + 0.5)) / n;
      exact += Math.hypot(a + b * th, b) * (turns / n);
    }
    const r = developedLength(pts, false, { kind: "flat", w: 20, t: 5, onEdge: false }, "centre");
    expect(Math.abs(r.neutral - exact)).toBeLessThan(0.01);
  });

  it("adds allowances, losses and the bar's weight", () => {
    const line: Point[] = [[0, 0], [300, 0]];
    const r = developedLength(line, false, { kind: "square", a: 12 }, "centre", 0.5, 20, 5);
    expect(r.neutral).toBeCloseTo(300, 9);
    expect(r.cut).toBeCloseTo(300 + 20 + 15, 9);
    // 12 × 12 × 335 mm of steel at 7.85 g/cm³
    expect(r.weightG).toBeCloseTo((144 * 335 * 7.85) / 1000, 6);
    expect(sectionArea({ kind: "flat", w: 30, t: 6, onEdge: true })).toBe(180);
  });

  it("finds the bar length holding a forged part's volume", () => {
    // a 60 cm³ blade from 25 × 6 flat bar, 8 % lost to scale
    expect(forgingStock(60000, { kind: "flat", w: 25, t: 6, onEdge: false }, 8)).toBeCloseTo(432, 6);
  });
});
