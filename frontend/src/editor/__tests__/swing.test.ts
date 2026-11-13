import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { circleNodes } from "../drafting";
import { EditorEngine } from "../engine";
import { outlineDistance, sweepAngles } from "../swing";
import type { DesignDocument, DocNode } from "../types";

const node = (x: number, y: number): DocNode => ({ x, y, ix: 0, iy: 0, ox: 0, oy: 0 });
const rect = (x: number, y: number, w: number, h: number) => [node(x, y), node(x + w, y), node(x + w, y + h), node(x, y + h)];

describe("swing helpers", () => {
  it("measures the gap between two outlines", () => {
    const a: [number, number][] = [[0, 0], [10, 0], [10, 10], [0, 10]];
    const b: [number, number][] = [[13, 2], [20, 2], [20, 8], [13, 8]];
    expect(outlineDistance(a, b)).toBeCloseTo(3, 12);
  });

  it("steps the sweep and always ends on the target angle", () => {
    expect(sweepAngles(2, 0.5)).toEqual([0, 0.5, 1, 1.5, 2]);
    const back = sweepAngles(-1.2, 0.5);
    expect(back[0]).toBe(0);
    expect(back[back.length - 1]).toBeCloseTo(-1.2, 12);
  });
});

describe("checking a blade's swing", () => {
  let engine: EditorEngine;
  const LAYERS: DesignDocument["layers"] = [
    { id: "cut", name: "Découpe", role: "cut", visible: true, locked: false },
    { id: "holes", name: "Perçages", role: "hole", visible: true, locked: false },
  ];
  beforeEach(() => {
    engine = new EditorEngine(document.createElement("canvas"), { headless: true });
    engine.loadDocument({
      version: 1,
      unit: "mm",
      layers: LAYERS,
      objects: [
        // an 80 × 10 blade, pivot hole at (5, 5)
        { id: "blade", type: "path", layer: "cut", name: "Lame", closed: true, contours: [rect(0, 0, 80, 10)] },
        { id: "pivot", type: "path", layer: "holes", name: "Pivot", closed: true, contours: [circleNodes(5, 5, 1.5)] },
        // stop pin above the pivot: the blade meets it while opening (y up for the user)
        { id: "stop", type: "path", layer: "holes", name: "Butée", closed: true, contours: [circleNodes(30, -20, 1.5)] },
        // a spring 2 mm below the closed blade
        { id: "spring", type: "path", layer: "cut", name: "Ressort", closed: true, contours: [rect(10, 12, 60, 4)] },
        // handle outlines: one that holds the closed blade with 1 mm to spare, one 3 mm too short
        { id: "handle", type: "path", layer: "cut", name: "Plaquette", closed: true, contours: [rect(-1, -1, 82, 12)] },
        { id: "short", type: "path", layer: "cut", name: "Courte", closed: true, contours: [rect(-1, -1, 78, 12)] },
      ],
    });
  });
  afterEach(() => engine.destroy());

  it("finds the pivot axis from the pivot hole", () => {
    const [x, y] = engine.centreOf("pivot")!;
    expect(x).toBeCloseTo(5, 4);
    expect(y).toBeCloseTo(5, 4);
  });

  it("reports the first contact while opening", () => {
    const r = engine.checkSwing("blade", [5, 5], 90, ["stop", "spring"]);
    expect(r.contact?.name).toBe("Butée");
    // the blade's top edge reaches the pin centre's line around atan(25/25) = 45°, minus the half-widths
    expect(r.contact!.angle).toBeGreaterThan(25);
    expect(r.contact!.angle).toBeLessThan(50);
  });

  it("gives the clearance at the end of the travel when nothing touches", () => {
    const r = engine.checkSwing("blade", [5, 5], 0, ["spring"]);
    expect(r.contact).toBeNull();
    expect(r.clearance?.name).toBe("Ressort");
    expect(r.clearance!.mm).toBeCloseTo(2, 3);
  });

  it("checks the closed blade stays inside the handle, with its margin", () => {
    const inside = engine.checkClosed("blade", [5, 5], 0, "handle")!;
    expect(inside.protrusion).toBe(0);
    expect(inside.margin).toBeCloseTo(1, 3);
    const out = engine.checkClosed("blade", [5, 5], 0, "short")!;
    expect(out.margin).toBe(0);
    expect(out.protrusion).toBeCloseTo(3, 3); // the tip sticks out 80 - 77 = 3 mm
  });
});
