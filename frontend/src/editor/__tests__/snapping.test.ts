import paper from "paper";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { EditorEngine, measure, type Measurement } from "../engine";
import type { DesignDocument, DocNode, PathObject } from "../types";
import { gridSteps } from "../view";

const node = (x: number, y: number, ix = 0, iy = 0, ox = 0, oy = 0): DocNode => ({ x, y, ix, iy, ox, oy });
const K = 0.5522847498;
const rect = (x: number, y: number, w: number, h: number) => [node(x, y), node(x + w, y), node(x + w, y + h), node(x, y + h)];
function circle(cx: number, cy: number, r: number): DocNode[] {
  const k = Math.round(K * r * 1e4) / 1e4;
  return [node(cx + r, cy, 0, -k, 0, k), node(cx, cy + r, k, 0, -k, 0), node(cx - r, cy, 0, k, 0, -k), node(cx, cy - r, -k, 0, k, 0)];
}
const path = (id: string, layer: string, contours: DocNode[][]): PathObject => ({ id, type: "path", layer, name: null, closed: true, contours });
function doc(objects: PathObject[]): DesignDocument {
  return {
    version: 1,
    unit: "mm",
    layers: [
      { id: "cut", name: "Découpe", role: "cut", visible: true, locked: false },
      { id: "holes", name: "Perçages", role: "hole", visible: true, locked: false },
      { id: "dimensions", name: "Cotes", role: "dimension", visible: true, locked: false },
    ],
    objects,
  };
}
const P = (x: number, y: number) => new paper.Point(x, y);
const mods = { shift: false, alt: false, ctrl: false };

let engine: EditorEngine;
beforeEach(() => {
  const canvas = document.createElement("canvas");
  canvas.width = 800;
  canvas.height = 600;
  engine = new EditorEngine(canvas, { headless: true });
  // zoom 4 px/mm: the 10 px snap radius is 2.5 mm
});
afterEach(() => engine.destroy());

describe("smart snapping", () => {
  beforeEach(() => {
    engine.loadDocument(doc([path("plate", "cut", [rect(0, 0, 40, 20)]), path("pin", "holes", [circle(50.3, 10.7, 4)])]));
  });

  it("prefers a node, then the midpoint of a segment", () => {
    expect(engine.snap(P(0.6, 0.7))).toMatchObject({ x: 0, y: 0 });
    expect(engine.lastSnap?.kind).toBe("node");
    expect(engine.snap(P(20.9, 0.8))).toMatchObject({ x: 20, y: 0 });
    expect(engine.lastSnap?.kind).toBe("midpoint");
  });

  it("finds the exact centre of a pin hole, off the grid", () => {
    const p = engine.snap(P(50.9, 11.4));
    expect(engine.lastSnap?.kind).toBe("center");
    expect(p.x).toBeCloseTo(50.3, 9);
    expect(p.y).toBeCloseTo(10.7, 9);
  });

  it("finds intersections between outlines", () => {
    engine.loadDocument(doc([path("a", "cut", [rect(0, 0, 40, 20)]), path("b", "cut", [rect(13.3, -5, 10, 40)])]));
    const p = engine.snap(P(14.1, 0.9));
    expect(engine.lastSnap?.kind).toBe("intersection");
    expect(p.x).toBeCloseTo(13.3, 9);
    expect(p.y).toBeCloseTo(0, 9);
  });

  it("snaps onto an outline only when asked to", () => {
    expect(engine.snap(P(30.4, 1.1))).toMatchObject({ x: 30, y: 1 }); // grid
    engine.snapOptions.path = true;
    const p = engine.snap(P(30.4, 1.1));
    expect(engine.lastSnap?.kind).toBe("path");
    expect(p.x).toBeCloseTo(30.4, 9);
    expect(p.y).toBeCloseTo(0, 9);
  });

  it("ignores hidden and locked layers, and every option can be turned off", () => {
    engine.updateLayer("holes", { visible: false });
    engine.snap(P(50.9, 11.4));
    expect(engine.lastSnap).toBeNull();
    engine.snapOptions = { nodes: false, intersections: false, midpoints: false, centers: false, path: false, guides: false, grid: false };
    expect(engine.snap(P(0.6, 0.7))).toMatchObject({ x: 0.6, y: 0.7 });
  });
});

describe("grid and guides", () => {
  it("accepts any grid step and snaps to it", () => {
    engine.setGridSize(0.25);
    expect(engine.gridSize).toBe(0.25);
    expect(engine.snap(P(10.13, 3.85))).toMatchObject({ x: 10.25, y: 3.75 });
    engine.setGridSize(0);
    engine.setGridSize(Number.NaN);
    expect(engine.gridSize).toBe(0.25); // invalid steps are ignored
  });

  it("a guide wins over the grid on its own axis only", () => {
    engine.addGuide("x", 12.34);
    const p = engine.snap(P(12.9, 40.4));
    expect(p.x).toBeCloseTo(12.34, 9);
    expect(p.y).toBe(40);
    expect(engine.lastSnap?.kind).toBe("guide");
  });

  it("guides are saved with the document and undoable, and absent when there are none", () => {
    expect(engine.exportDocument().guides).toBeUndefined();
    engine.addGuide("y", 25);
    engine.addGuide("x", -3.5);
    expect(engine.exportDocument().guides).toEqual([{ axis: "y", pos: 25 }, { axis: "x", pos: -3.5 }]);
    engine.moveGuide(0, 30);
    engine.undo();
    expect(engine.guides[0].pos).toBe(25);
    engine.removeGuide(1);
    expect(engine.guides).toEqual([{ axis: "y", pos: 25 }]);
    engine.loadDocument({ ...doc([]), guides: [{ axis: "x", pos: 7 }] });
    expect(engine.guides).toEqual([{ axis: "x", pos: 7 }]);
  });

  it("the drawn grid is the snap grid, thinned out when too dense", () => {
    expect(gridSteps(14, 1)).toEqual({ minor: 1, major: 10 }); // 1 mm squares, centimetre lines
    expect(gridSteps(4, 1)).toEqual({ minor: 2, major: 10 });
    expect(gridSteps(1, 1)).toEqual({ minor: 10, major: 100 });
    const fine = gridSteps(140, 0.1);
    expect(fine.minor).toBeCloseTo(0.1, 12);
    expect(fine.major).toBeCloseTo(1, 12);
  });
});

describe("angle constraint (Shift)", () => {
  it("locks the direction to 15° steps and the length to the grid", () => {
    const from = P(0, 0);
    expect(engine.snap(P(10.2, 0.8), [], { from, constrain: true })).toMatchObject({ x: 10, y: 0 });
    const p = engine.snap(P(7, 7.4), [], { from, constrain: true });
    // 45°, length 10.19 rounded to the 1 mm grid = 10
    expect(p.x).toBeCloseTo(7.0711, 4);
    expect(p.y).toBeCloseTo(7.0711, 4);
    expect(engine.lastSnap?.kind).toBe("angle");
  });

  it("the pen tool uses it from the previous node", () => {
    engine.setTool("pen");
    const h = engine.activeHandler;
    h.down(P(0, 0), mods);
    h.up(P(0, 0), mods);
    h.down(P(30.4, 1.9), { ...mods, shift: true });
    h.up(P(30.4, 1.9), mods);
    h.key("Enter");
    const obj = engine.exportDocument().objects[0] as PathObject;
    expect(obj.contours[0][1]).toMatchObject({ x: 30, y: 0 });
  });
});

describe("measure", () => {
  it("computes distance, components and a drawing-style angle (y up)", () => {
    const m = measure(P(0, 0), P(30, -40));
    expect(m.distance).toBe(50);
    expect([m.dx, m.dy]).toEqual([30, -40]);
    expect(m.angle).toBeCloseTo(53.1, 1); // going up on screen = positive angle
    expect(measure(P(0, 0), P(-10, 0)).angle).toBe(180);
    expect(measure(P(0, 0), P(0, 10)).angle).toBe(-90);
  });

  it("the tool measures between two snapped clicks and turns it into a dimension", () => {
    engine.loadDocument(doc([path("plate", "cut", [rect(0, 0, 40, 20)])]));
    const readings: (Measurement | null)[] = [];
    engine.on("measure", (m) => readings.push(m));
    engine.setTool("measure");
    const h = engine.activeHandler;
    h.down(P(0.7, 0.4), mods); // node (0, 0)
    h.down(P(39.2, 19.6), mods); // node (40, 20)
    const m = readings[readings.length - 1]!;
    expect(m.a).toEqual([0, 0]);
    expect(m.b).toEqual([40, 20]);
    expect(m.distance).toBeCloseTo(Math.hypot(40, 20), 12);
    expect(h.key("Enter")).toBe(true);
    const dim = engine.exportDocument().objects.find((o) => o.type === "dimension");
    expect(dim).toMatchObject({ a: [0, 0], b: [40, 20], layer: "dimensions" });
    engine.undo();
    expect(engine.exportDocument().objects.some((o) => o.type === "dimension")).toBe(false);
  });
});

describe("reference image", () => {
  const image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
  const state = { image, cx: 50, cy: 20, width_mm: 100, height_mm: 50, rotation_deg: 0, opacity: 0.5, visible: true, locked: true, calibrated: false };

  it("is never part of the document, its history or its dirty state", () => {
    engine.loadDocument(doc([path("plate", "cut", [rect(0, 0, 40, 20)])]));
    const before = JSON.stringify(engine.exportDocument());
    engine.setBackground(state);
    engine.updateBackground({ opacity: 0.8, cx: 12 });
    expect(JSON.stringify(engine.exportDocument())).toBe(before);
    expect(engine.dirty).toBe(false);
    expect(engine.canUndo).toBe(false);
    expect(engine.docItems().length).toBe(1);
    expect(engine.background).toMatchObject({ opacity: 0.8, cx: 12 });
  });

  it("calibration tool hands over the raw clicked points, not grid-snapped ones", () => {
    engine.setBackground(state);
    const picked: [number, number][][] = [];
    engine.on("calibrate", (a, b) => picked.push([a, b]));
    engine.setTool("calibrate");
    engine.activeHandler.down(P(10.37, 10.21), mods);
    engine.activeHandler.down(P(60.74, 10.18), mods);
    expect(picked).toEqual([[[10.37, 10.21], [60.74, 10.18]]]);
    engine.calibrateBackground(picked[0][0], picked[0][1], 100, "horizontal", false);
    expect(engine.background?.calibrated).toBe(true);
    expect(engine.background?.width_mm).toBeCloseTo((100 * 100) / Math.hypot(50.37, 0.03), 3);
  });

  it("the calibration tool does nothing without an image", () => {
    const picked: unknown[] = [];
    engine.on("calibrate", (...args) => picked.push(args));
    engine.setTool("calibrate");
    engine.activeHandler.down(P(0, 0), mods);
    engine.activeHandler.down(P(10, 0), mods);
    expect(picked).toEqual([]);
  });
});
