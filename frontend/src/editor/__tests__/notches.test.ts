import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { EditorEngine } from "../engine";
import { NOTCH_PRESETS, notchCentres, notchContours, roundNotchRadius } from "../notches";
import type { DesignDocument, DocNode } from "../types";

const node = (x: number, y: number): DocNode => ({ x, y, ix: 0, iy: 0, ox: 0, oy: 0 });

describe("notch geometry", () => {
  it("centres the row on the stretch, the end notches inside it", () => {
    const c = notchCentres({ a: [0, 0], b: [20, 0], pitch: 2, width: 1, depth: 0.5, shape: "v" });
    // usable 19 mm → 10 notches 2 mm apart (18 mm), centred on the 20 mm stretch: 1 … 19
    expect(c).toHaveLength(10);
    expect(c[0][0]).toBeCloseTo(1, 9);
    expect(c[9][0]).toBeCloseTo(19, 9);
    expect(c.every(([, y]) => y === 0)).toBe(true);
  });

  it("gives the round notch the exact radius for its opening and depth", () => {
    // chord 5.5, sagitta 1.6: R = 5.5²/8/1.6 + 0.8
    expect(roundNotchRadius(5.5, 1.6)).toBeCloseTo(3.1633, 4);
    // a half-circle: depth = half the width
    expect(roundNotchRadius(4, 2)).toBe(2);
  });

  it("opens the V exactly `width` wide at the edge and `depth` deep", () => {
    const [v] = notchContours({ a: [0, 0], b: [3, 0], pitch: 3, width: 1.2, depth: 0.6, shape: "v" }, [0, 1]);
    const [left, right, tip] = v;
    expect(tip.y).toBeCloseTo(0.6, 12);
    // the sides cross the edge line (y = 0) at ±0.6 around the centre x = 1.5
    const crossing = (p: DocNode, q: DocNode) => p.x + ((q.x - p.x) * (0 - p.y)) / (q.y - p.y);
    expect(crossing(left, tip)).toBeCloseTo(1.5 - 0.6, 12);
    expect(crossing(right, tip)).toBeCloseTo(1.5 + 0.6, 12);
  });
});

describe("cutting notches into a part", () => {
  let engine: EditorEngine;
  const LAYERS: DesignDocument["layers"] = [{ id: "cut", name: "Découpe", role: "cut", visible: true, locked: false }];

  beforeEach(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 800;
    canvas.height = 600;
    engine = new EditorEngine(canvas, { headless: true });
    // a 100 × 30 spine bar, material below y = 0
    engine.loadDocument({ version: 1, unit: "mm", layers: LAYERS, objects: [{ id: "bar", type: "path", layer: "cut", name: "Lame", closed: true, contours: [[node(0, 0), node(100, 0), node(100, 30), node(0, 30)]] }] });
    engine.selectById(["bar"]);
  });
  afterEach(() => engine.destroy());

  it("removes the notch area from the material side, whatever the direction A→B", () => {
    const before = 100 * 30;
    // V notches 1.2 × 0.6: each removes 0.36 mm²
    const n = engine.cutNotches({ a: [80, 0], b: [60, 0], ...NOTCH_PRESETS.jimping });
    expect(n).toBe(10);
    const [obj] = engine.exportDocument().objects;
    const item = engine.itemById(obj.id)!;
    expect(engine.evenOddArea(item)).toBeCloseTo(before - 10 * 0.36, 3);
    expect(item.bounds.top).toBeCloseTo(0, 6); // nothing added above the edge
    expect((obj as { name: string }).name).toBe("Lame");
  });

  it("refuses a stretch that does not follow the outline", () => {
    expect(engine.cutNotches({ a: [20, 15], b: [40, 15], ...NOTCH_PRESETS.jimping })).toBe("notOnEdge");
    engine.selectById([]);
    expect(engine.cutNotches({ a: [20, 0], b: [40, 0], ...NOTCH_PRESETS.jimping })).toBe("noPart");
  });
});

describe("notches along a curve", () => {
  let engine: EditorEngine;
  const LAYERS: DesignDocument["layers"] = [{ id: "cut", name: "Découpe", role: "cut", visible: true, locked: false }];
  const K = 0.5522847498;
  const R = 40;
  const disc = (r: number): DocNode[] => {
    const k = K * r;
    return [
      { x: r, y: 0, ix: 0, iy: -k, ox: 0, oy: k },
      { x: 0, y: r, ix: k, iy: 0, ox: -k, oy: 0 },
      { x: -r, y: 0, ix: 0, iy: k, ox: 0, oy: -k },
      { x: 0, y: -r, ix: -k, iy: 0, ox: k, oy: 0 },
    ];
  };

  beforeEach(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 800;
    canvas.height = 600;
    engine = new EditorEngine(canvas, { headless: true });
    engine.loadDocument({ version: 1, unit: "mm", layers: LAYERS, objects: [{ id: "d", type: "path", layer: "cut", name: "Disque", closed: true, contours: [disc(R)] }] });
    engine.selectById(["d"]);
  });
  afterEach(() => engine.destroy());

  it("spaces the notches by arc length and keeps each square to the edge", () => {
    const item = engine.itemById("d")!;
    const before = engine.evenOddArea(item);
    // a quarter of the rim, from (R, 0) to (0, R): arc length πR/2 ≈ 62.83 mm
    const pattern = { a: [R, 0] as [number, number], b: [0, R] as [number, number], pitch: 2, width: 1, depth: 0.5, shape: "square" as const };
    const n = engine.cutNotches(pattern, true);
    // usable 61.83 mm → 31 notches 2 mm apart
    expect(n).toBe(31);
    const after = engine.evenOddArea(engine.itemById(engine.exportDocument().objects[0].id)!);
    // each square slot removes ≈ width × depth, a little less on a convex rim (≤ 1 %)
    const removed = before - after;
    expect(removed / (31 * 0.5)).toBeGreaterThan(0.98);
    expect(removed / (31 * 0.5)).toBeLessThan(1.01);
  });

  it("follows the outline the shorter way, and refuses points off it", () => {
    expect(engine.cutNotches({ a: [R, 0], b: [0, R], ...NOTCH_PRESETS.jimping }, true)).toBeGreaterThan(20);
    engine.selectById([engine.exportDocument().objects[0].id]);
    expect(engine.cutNotches({ a: [R - 3, 0], b: [0, R], ...NOTCH_PRESETS.jimping }, true)).toBe("notOnEdge");
  });

  it("builds every notch in the frame it is given", async () => {
    const { notchContoursAt, notchOffsets } = await import("../notches");
    expect(notchOffsets(10, 2, 1)).toEqual([1, 3, 5, 7, 9]);
    // a square slot on a frame turned 90°: the edge runs along y, material towards -x
    const [slot] = notchContoursAt({ width: 2, depth: 1, shape: "square" }, [{ c: [5, 5], u: [0, 1], n: [-1, 0] }]);
    const xs = slot.map((p) => p.x);
    expect(Math.min(...xs)).toBeCloseTo(4, 12); // 1 mm into the material
    expect(Math.max(...xs)).toBeCloseTo(6, 12); // 1 mm overshoot outside
  });
});
