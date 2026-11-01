import { readFileSync } from "node:fs";
import { join } from "node:path";

import opentype from "opentype.js";
import { describe, expect, it } from "vitest";

import { commandsToContours, missingGlyphs, textContours } from "../text";

/** The bundled font file, the same one the editor loads. */
const fontFile = (name: string) => {
  const buf = readFileSync(join(process.cwd(), "node_modules/@fontsource/inter/files", name)); // tests run from frontend/
  return opentype.parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
};
const bounds = (contours: { x: number; y: number }[][]) => {
  const pts = contours.flat();
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
};

describe("path commands to contours", () => {
  it("converts a quadratic segment to the exactly equivalent cubic", () => {
    const [c] = commandsToContours([
      { type: "M", x: 0, y: 0 },
      { type: "Q", x1: 10, y1: 10, x: 20, y: 0 },
      { type: "L", x: 10, y: -5 },
      { type: "Z" },
    ] as opentype.PathCommand[]);
    expect(c[0]).toMatchObject({ x: 0, y: 0, ox: 6.6667, oy: 6.6667 });
    expect(c[1]).toMatchObject({ x: 20, y: 0, ix: -6.6667, iy: 6.6667 });
    // the cubic's midpoint is the quadratic's midpoint (10, 5)
    const mid = 0.125 * 0 + 0.375 * (0 + 6.6667) + 0.375 * (20 - 6.6667) + 0.125 * 20;
    expect(mid).toBeCloseTo(10, 3);
  });

  it("merges the closing point into the start and drops degenerate contours", () => {
    const out = commandsToContours([
      { type: "M", x: 0, y: 0 },
      { type: "L", x: 10, y: 0 },
      { type: "L", x: 10, y: 10 },
      { type: "L", x: 0, y: 0 },
      { type: "Z" },
      { type: "M", x: 50, y: 50 },
      { type: "L", x: 51, y: 50 },
      { type: "Z" },
    ] as opentype.PathCommand[]);
    expect(out.length).toBe(1);
    expect(out[0].length).toBe(3);
  });
});

describe("text with the bundled font", () => {
  const font = fontFile("inter-latin-400-normal.woff");

  it("makes capitals exactly the requested height, sitting on the baseline", () => {
    const b = bounds(textContours(font, "HELL", { x: 10, y: 50, capHeight: 6 }));
    expect(b.maxY).toBeCloseTo(50, 3); // flat bottoms of H, E, L on the baseline
    expect(b.maxY - b.minY).toBeCloseTo(6, 3); // flat tops at cap height
    expect(b.minX).toBeGreaterThanOrEqual(10);
  });

  it("keeps the counters of letters as separate contours, and spaces letters on request", () => {
    expect(textContours(font, "o", { x: 0, y: 0, capHeight: 5 }).length).toBe(2);
    const tight = bounds(textContours(font, "II", { x: 0, y: 0, capHeight: 5 }));
    const wide = bounds(textContours(font, "II", { x: 0, y: 0, capHeight: 5, letterSpacing: 2 }));
    expect(wide.maxX - tight.maxX).toBeCloseTo(2, 3);
  });

  it("covers French accents and reports what it cannot draw", () => {
    expect(missingGlyphs(font, "Forgé à la main — Œuvre n° 12")).toEqual([]);
    expect(missingGlyphs(font, "刀 OK")).toEqual(["刀"]);
  });
});
