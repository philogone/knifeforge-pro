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
