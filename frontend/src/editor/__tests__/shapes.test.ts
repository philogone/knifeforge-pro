import { describe, expect, it } from "vitest";

import { SHAPES, documentParts, ellipse, normalizeParams, partsBounds, placeParts, roundedRect, type ShapePart } from "../shapes";
import type { DesignDocument, DocNode } from "../types";

/** Exact area of a closed Bézier contour (Green's theorem on each cubic). */
function area(nodes: DocNode[]): number {
  let a = 0;
  for (let i = 0; i < nodes.length; i++) {
    const p = nodes[i];
    const q = nodes[(i + 1) % nodes.length];
    const [x0, y0, x1, y1, x2, y2, x3, y3] = [p.x, p.y, p.x + p.ox, p.y + p.oy, q.x + q.ix, q.y + q.iy, q.x, q.y];
    a += (3 / 20) * (x0 * (6 * y1 + 3 * y2 + y3 - 10 * y0) + x1 * (-6 * y0 + 3 * y2 + 3 * y3) + x2 * (-3 * y0 - 3 * y1 + 6 * y3) + x3 * (-y0 - 3 * y1 - 6 * y2 + 10 * y3)) / 3;
  }
  return Math.abs(a);
}

const build = (key: string, values: Record<string, number> = {}) => {
  const def = SHAPES.find((d) => d.key === key)!;
  return def.build(normalizeParams(def, { ...Object.fromEntries(def.params.map((p) => [p.key, p.value])), ...values }));
};
const byRole = (parts: ShapePart[], role: string) => parts.filter((p) => p.role === role);

describe("primitives", () => {
  it("rounds rectangle corners with true quarter circles", () => {
    const r = roundedRect(0, 0, 110, 25, 6);
    expect(r.length).toBe(8);
    // a circle quarter made of one Bézier is 0.027 % off radially: well under 0.01 mm here
    expect(area(r)).toBeCloseTo(110 * 25 - (4 - Math.PI) * 36, 1);
    expect(partsBounds([{ role: "cut", name: "", closed: true, contours: [r] }])).toEqual({ minX: 0, minY: 0, maxX: 110, maxY: 25 });
  });

  it("makes a stadium when the radius is half the height, without doubled nodes", () => {
    const s = roundedRect(0, 0, 40, 10, 99);
    expect(s.length).toBe(6);
    for (let i = 0; i < s.length; i++) {
      const q = s[(i + 1) % s.length];
      expect(Math.hypot(q.x - s[i].x, q.y - s[i].y)).toBeGreaterThan(1);
    }
    expect(area(s)).toBeCloseTo(30 * 10 + Math.PI * 25, 1);
  });

  it("draws an ellipse through its extreme points", () => {
    expect(area(ellipse(0, 0, 21, 8))).toBeCloseTo(Math.PI * 21 * 8, 0);
  });
});

describe("library shapes", () => {
  it("handle scale: outline on the cut layer and evenly spaced pin holes", () => {
    const parts = build("handleScale", { length: 100, pins: 3, inset: 10, pinD: 4 });
    expect(byRole(parts, "cut").length).toBe(1);
    const holes = byRole(parts, "hole");
    expect(holes.map((h) => (Math.max(...h.contours[0].map((n) => n.x)) + Math.min(...h.contours[0].map((n) => n.x))) / 2)).toEqual([10, 50, 90]);
    expect(holes.every((h) => Math.max(...h.contours[0].map((n) => n.x)) - Math.min(...h.contours[0].map((n) => n.x)) === 4)).toBe(true);
  });

  it("washer: a bore smaller than the outside, none when solid", () => {
    expect(byRole(build("washer", { outer: 20, inner: 6.35 }), "hole").length).toBe(1);
    expect(byRole(build("washer", { outer: 20, inner: 0 }), "hole").length).toBe(0);
    expect(byRole(build("washer", { outer: 20, inner: 25 }), "hole").length).toBe(0);
  });

  it("blades come with an open grind line inside the blade, unless its height is 0", () => {
    for (const key of ["dropPoint", "wharncliffe"]) {
      const parts = build(key);
      const [blade] = byRole(parts, "cut");
      const [grind] = byRole(parts, "grind");
      expect(grind.closed).toBe(false);
      const b = partsBounds([blade])!;
      const g = partsBounds([grind])!;
      expect(g.minX).toBeGreaterThanOrEqual(b.minX);
      expect(g.maxX).toBeLessThanOrEqual(b.maxX + 1e-9);
      expect(g.maxY).toBeLessThanOrEqual(b.maxY + 1e-9);
      expect(byRole(build(key, { grind: 0 }), "grind").length).toBe(0);
    }
  });

  it("every shape builds valid geometry at its bounds, including a blade without tang", () => {
    for (const def of SHAPES) {
      for (const pick of ["min", "max"] as const) {
        const parts = def.build(normalizeParams(def, Object.fromEntries(def.params.map((p) => [p.key, p[pick]]))));
        for (const part of parts) {
          for (const c of part.contours) {
            expect(c.length).toBeGreaterThanOrEqual(2);
            expect(c.every((n) => Object.values(n).every(Number.isFinite))).toBe(true);
          }
        }
      }
    }
  });

  it("clamps parameters and rounds counts", () => {
    const def = SHAPES.find((d) => d.key === "handleScale")!;
    const p = normalizeParams(def, { length: -5, pins: 2.6, width: "abc" });
    expect(p.length).toBe(10);
    expect(p.pins).toBe(3);
    expect(p.width).toBe(25);
  });
});

describe("placing and reusing", () => {
  it("moves parts so their top-left corner lands on the requested point", () => {
    const placed = placeParts(build("ovalGuard"), 100, -20);
    const b = partsBounds(placed)!;
    expect([b.minX, b.minY]).toEqual([100, -20]);
  });

  it("takes the drawn parts of another design, not its guides, dimensions or construction", () => {
    const doc: DesignDocument = {
      version: 1,
      unit: "mm",
      layers: [
        { id: "c", name: "Découpe", role: "cut", visible: true, locked: false },
        { id: "k", name: "Construction", role: "construction", visible: true, locked: false },
        { id: "g", name: "Émouture", role: "grind", visible: true, locked: false },
        { id: "d", name: "Cotes", role: "dimension", visible: true, locked: false },
      ],
      objects: [
        { id: "a", type: "path", layer: "c", name: "Lame", closed: true, contours: [roundedRect(0, 0, 10, 10, 0)] },
        { id: "b", type: "path", layer: "k", name: null, closed: false, contours: [roundedRect(0, 0, 10, 10, 0)] },
        { id: "e", type: "path", layer: "g", name: null, closed: false, contours: [roundedRect(0, 0, 5, 5, 0)] },
        { id: "f", type: "dimension", layer: "d", a: [0, 0], b: [10, 0], offset: 8, label: null },
      ],
    };
    expect(documentParts(doc).map((p) => [p.role, p.name])).toEqual([
      ["cut", "Lame"],
      ["grind", ""],
    ]);
  });
});
