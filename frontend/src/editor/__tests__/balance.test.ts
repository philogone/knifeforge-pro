import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { DENSITIES, areaAndCentroid, guessDensity, massProperties } from "../balance";
import { EditorEngine } from "../engine";
import type { DesignDocument, DocNode } from "../types";

const square = (x: number, y: number, s: number): [number, number][] => [[x, y], [x + s, y], [x + s, y + s], [x, y + s]];

describe("mass and balance", () => {
  it("computes area and centroid, inner rings removed whatever their winding", () => {
    const plate = square(0, 0, 100);
    const hole = square(10, 40, 20).reverse(); // same winding or not, nested = cut-out
    const { area, centre } = areaAndCentroid([plate, hole]);
    expect(area).toBeCloseTo(10000 - 400, 9);
    // moment: 10000·50 − 400·20 on x
    expect(centre[0]).toBeCloseTo((10000 * 50 - 400 * 20) / 9600, 9);
    expect(centre[1]).toBeCloseTo(50, 9);
  });

  it("weighs a steel blade and a wooden handle, balance between the two", () => {
    // blade 100 × 30 × 4 mm steel, handle 100 × 30 × 15 mm wood placed after it
    const r = massProperties([
      { id: "blade", rings: [[[0, 0], [100, 0], [100, 30], [0, 30]]], thicknessMm: 4, density: DENSITIES.carbon_steel },
      { id: "handle", rings: [[[100, 0], [200, 0], [200, 30], [100, 30]]], thicknessMm: 15, density: DENSITIES.wood },
    ]);
    const blade = 3000 * 4 * 7.85 / 1000; // 94.2 g
    const handle = 3000 * 15 * 0.75 / 1000; // 33.75 g
    expect(r.massG).toBeCloseTo(blade + handle, 9);
    expect(r.centre![0]).toBeCloseTo((blade * 50 + handle * 150) / (blade + handle), 9);
  });

  it("guesses densities from the stock material", () => {
    expect(guessDensity({ category: "blade_steel", metal_type: "titanium", name: "Ti 6Al-4V" })).toBe(DENSITIES.titanium);
    expect(guessDensity({ category: "handle_material", metal_type: null, name: "G10 Sheet, Black" })).toBe(DENSITIES.g10);
    expect(guessDensity({ category: "handle_material", metal_type: null, name: "Walnut Handle Scales", wood_species: "Noyer" })).toBe(DENSITIES.wood);
    expect(guessDensity({ category: "blade_steel", metal_type: null, name: "1095" })).toBe(DENSITIES.carbon_steel);
  });
});

describe("plate parts from the drawing", () => {
  let engine: EditorEngine;
  const node = (x: number, y: number): DocNode => ({ x, y, ix: 0, iy: 0, ox: 0, oy: 0 });
  const LAYERS: DesignDocument["layers"] = [
    { id: "cut", name: "Découpe", role: "cut", visible: true, locked: false },
    { id: "holes", name: "Perçages", role: "hole", visible: true, locked: false },
  ];
  beforeEach(() => {
    const canvas = document.createElement("canvas");
    engine = new EditorEngine(canvas, { headless: true });
  });
  afterEach(() => engine.destroy());

  it("deducts the holes lying inside a part", () => {
    engine.loadDocument({
      version: 1,
      unit: "mm",
      layers: LAYERS,
      objects: [
        { id: "tang", type: "path", layer: "cut", name: "Soie", closed: true, contours: [[node(0, 0), node(100, 0), node(100, 20), node(0, 20)]] },
        { id: "pin", type: "path", layer: "holes", name: null, closed: true, contours: [[node(40, 5), node(50, 5), node(50, 15), node(40, 15)]] },
        { id: "away", type: "path", layer: "holes", name: null, closed: true, contours: [[node(200, 5), node(210, 5), node(210, 15), node(200, 15)]] },
      ],
    });
    const [part] = engine.plateParts();
    expect(part.name).toBe("Soie");
    const { area } = areaAndCentroid(part.rings);
    expect(area).toBeCloseTo(2000 - 100, 6);
  });
});
