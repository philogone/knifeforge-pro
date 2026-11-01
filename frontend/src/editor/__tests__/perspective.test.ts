import { describe, expect, it } from "vitest";

import {
  applyHomography,
  docToPixel,
  isConvexQuad,
  planRectify,
  rectangleTargets,
  rectifiedPlacement,
  signedArea2,
  solveHomography,
  warpPixels,
  type Mat3,
  type Pt,
} from "../perspective";

// a strong, realistic perspective: a sheet photographed from the side and above
const TRUE_H: Mat3 = [9.2, 1.1, 410, -0.6, 7.4, 380, 0.0021, 0.0009, 1];
const map = (p: Pt) => applyHomography(TRUE_H, p)!;

describe("homography", () => {
  it("is recovered exactly from four correspondences and maps every other point the same way", () => {
    const rect: Pt[] = [[0, 0], [297, 0], [297, 210], [0, 210]];
    const h = solveHomography(rect, rect.map(map))!;
    for (const p of [[10, 20], [150, 105], [296, 1], [-40, 250]] as Pt[]) {
      const a = applyHomography(h, p)!;
      const b = map(p);
      expect(Math.hypot(a[0] - b[0], a[1] - b[1])).toBeLessThan(1e-7);
    }
  });

  it("refuses aligned points", () => {
    expect(solveHomography([[0, 0], [1, 1], [2, 2], [3, 3]], [[0, 0], [1, 0], [1, 1], [0, 1]])).toBeNull();
  });
});

describe("clicked quadrilateral", () => {
  it("must be convex, in click order", () => {
    expect(isConvexQuad([[0, 0], [10, 0], [10, 10], [0, 10]])).toBe(true);
    expect(isConvexQuad([[0, 0], [10, 10], [10, 0], [0, 10]])).toBe(false); // bow-tie: wrong order
    expect(isConvexQuad([[0, 0], [10, 0], [2, 2], [0, 10]])).toBe(false); // dented
    expect(isConvexQuad([[0, 0], [5, 0], [10, 0], [0, 10]])).toBe(false); // three aligned
  });

  it("keeps the first side's direction and never mirrors, whichever way the corners are clicked", () => {
    // clockwise on screen, first side to the right
    expect(rectangleTargets([[0, 0], [100, 3], [98, 60], [-2, 58]], 297, 210)).toEqual([[0, 0], [297, 0], [297, 210], [0, 210]]);
    // anticlockwise on screen: first side goes down, the rectangle opens to the right
    const ccw: Pt[] = [[0, 0], [2, 60], [100, 62], [98, 1]];
    const t = rectangleTargets(ccw, 210, 297);
    expect(t).toEqual([[0, 0], [0, 210], [297, 210], [297, 0]]);
    expect(Math.sign(signedArea2(t))).toBe(Math.sign(signedArea2(ccw)));
  });
});

describe("document point to image pixel", () => {
  it("inverts the image placement (centre, size, rotation)", () => {
    const bg = { cx: 50, cy: 20, width_mm: 200, height_mm: 100, rotation_deg: 90 };
    // rotated a quarter turn clockwise: the image's top-left corner is now at the top right
    const p = docToPixel(bg, 2000, 1000, [100, -80]);
    expect(p[0]).toBeCloseTo(0, 9);
    expect(p[1]).toBeCloseTo(0, 9);
    const c = docToPixel(bg, 2000, 1000, [50, 20]);
    expect(c).toEqual([1000, 500]);
  });
});

describe("rectification plan", () => {
  const rect: Pt[] = [[0, 0], [297, 0], [297, 210], [0, 210]];
  const pixels = rect.map(map);

  it("puts the four corners exactly on the rectangle, at the sharpest resolution of the photo", () => {
    const plan = planRectify(pixels, rect, 6000, 4000, { maxPx: 1e9, maxPixels: 1e12 })!;
    for (let i = 0; i < 4; i++) {
      const back = applyHomography(plan.toSource, rect[i])!;
      expect(Math.hypot(back[0] - pixels[i][0], back[1] - pixels[i][1])).toBeLessThan(1e-7);
    }
    const sides = [0, 1, 2, 3].map((i) => Math.hypot(pixels[(i + 1) % 4][0] - pixels[i][0], pixels[(i + 1) % 4][1] - pixels[i][1]) / (i % 2 ? 210 : 297));
    expect(plan.pxPerMm).toBeCloseTo(Math.max(...sides), 9);
    expect(plan.sourceMmPerPx).toBeCloseTo(1 / Math.min(...sides), 9);
  });

  it("is capped in size, and clipped around the rectangle", () => {
    const plan = planRectify(pixels, rect, 6000, 4000)!;
    expect(Math.max(plan.outWidth, plan.outHeight)).toBeLessThanOrEqual(4000);
    expect(plan.minX).toBeGreaterThanOrEqual(-1.5 * 297 - 1e-9);
    expect(plan.minY).toBeGreaterThanOrEqual(-1.5 * 297 - 1e-9);
  });

  it("places the corrected image so that corner 1 lands on the anchor, at exactly one scale", () => {
    const plan = planRectify(pixels, rect, 6000, 4000)!;
    const place = rectifiedPlacement(plan, [10, 20]);
    expect(place.rotation_deg).toBe(0);
    expect(place.cx - place.width_mm / 2).toBeCloseTo(10 + plan.minX, 3);
    expect(place.cy - place.height_mm / 2).toBeCloseTo(20 + plan.minY, 3);
    expect(place.width_mm / plan.outWidth).toBeCloseTo(place.height_mm / plan.outHeight, 6);
  });

  it("refuses a crossed quadrilateral", () => {
    expect(planRectify([pixels[0], pixels[2], pixels[1], pixels[3]], rect, 6000, 4000)).toBeNull();
  });
});

describe("resampling", () => {
  it("turns a photographed square back into a square", () => {
    // source: 400 × 300 photo of a black 40 × 40 mm square on white, seen in perspective
    const H: Mat3 = [3.2, 0.4, 90, -0.2, 2.9, 60, 0.0015, 0.0006, 1];
    const sw = 400;
    const sh = 300;
    const data = new Uint8ClampedArray(sw * sh * 4);
    const inv = (u: number, v: number): Pt => {
      // brute inverse via the solver: map pixel back to mm
      return applyHomography(toMm, [u, v])!;
    };
    const corners: Pt[] = [[0, 0], [40, 0], [40, 40], [0, 40]];
    const toMm = solveHomography(corners.map((p) => applyHomography(H, p)!), corners)!;
    for (let j = 0; j < sh; j++) {
      for (let i = 0; i < sw; i++) {
        const [x, y] = inv(i + 0.5, j + 0.5);
        const black = x >= 0 && x <= 40 && y >= 0 && y <= 40;
        data.set(black ? [0, 0, 0, 255] : [255, 255, 255, 255], (j * sw + i) * 4);
      }
    }
    const plan = planRectify(corners.map((p) => applyHomography(H, p)!), corners, sw, sh, { margin: 0.05 })!;
    const out = warpPixels({ data, width: sw, height: sh }, plan);
    // measure the dark square along its middle row and column in the output
    const dark = (i: number, j: number) => out.data[(j * out.width + i) * 4] < 128 && out.data[(j * out.width + i) * 4 + 3] > 0;
    const midRow = Math.round((20 - plan.minY) * plan.pxPerMm);
    const midCol = Math.round((20 - plan.minX) * plan.pxPerMm);
    let w = 0;
    for (let i = 0; i < out.width; i++) if (dark(i, midRow)) w++;
    let h = 0;
    for (let j = 0; j < out.height; j++) if (dark(midCol, j)) h++;
    // within two output pixels (the edges are blurred by the source's pixels)
    expect(Math.abs(w / plan.pxPerMm - 40)).toBeLessThan(2 / plan.pxPerMm);
    expect(Math.abs(h / plan.pxPerMm - 40)).toBeLessThan(2 / plan.pxPerMm);
  });

  it("clips the corrected image to the photo when the whole photo is in front of the camera", () => {
    const data = new Uint8ClampedArray(4 * 4 * 4).fill(255);
    const sq: Pt[] = [[1, 1], [3, 1], [3, 3], [1, 3]];
    const plan = planRectify(sq, [[0, 0], [10, 0], [10, 10], [0, 10]], 4, 4, { margin: 1 })!;
    const out = warpPixels({ data, width: 4, height: 4 }, plan);
    const alpha = (i: number, j: number) => out.data[(j * out.width + i) * 4 + 3];
    expect(alpha(Math.round(out.width / 2), Math.round(out.height / 2))).toBe(255);
    expect(out.data.some((_, k) => k % 4 === 3 && out.data[k] === 0)).toBe(false);
  });
});
