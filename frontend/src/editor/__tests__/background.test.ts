import { describe, expect, it } from "vitest";

import { calibrate, fitPixels, initialPlacement, mmPerPixel, normalizeDeg, type BackgroundPlacement } from "../background";

type Pt = [number, number];

// Independent model of the placement: a point of the image, in normalised image coordinates
// (u, v ∈ [-0.5, 0.5] around the centre), is at  centre + R(rotation) · (u·width, v·height).
function imageToWorld(bg: BackgroundPlacement, [u, v]: Pt): Pt {
  const r = (bg.rotation_deg * Math.PI) / 180;
  const x = u * bg.width_mm;
  const y = v * bg.height_mm;
  return [bg.cx + x * Math.cos(r) - y * Math.sin(r), bg.cy + x * Math.sin(r) + y * Math.cos(r)];
}

function worldToImage(bg: BackgroundPlacement, [px, py]: Pt): Pt {
  const r = (-bg.rotation_deg * Math.PI) / 180;
  const dx = px - bg.cx;
  const dy = py - bg.cy;
  return [(dx * Math.cos(r) - dy * Math.sin(r)) / bg.width_mm, (dx * Math.sin(r) + dy * Math.cos(r)) / bg.height_mm];
}

const dist = (a: Pt, b: Pt) => Math.hypot(b[0] - a[0], b[1] - a[1]);
const TOL = 1e-3; // mm: far below the 0.1 mm requirement (placement is stored to 4 decimals)

/** The same physical features of the photo, before and after calibration. */
function featuresAfter(before: BackgroundPlacement, after: BackgroundPlacement, a: Pt, b: Pt): [Pt, Pt] {
  return [imageToWorld(after, worldToImage(before, a)), imageToWorld(after, worldToImage(before, b))];
}

const photo: BackgroundPlacement = { cx: 40, cy: 30, width_mm: 100, height_mm: 75, rotation_deg: 0 };

describe("background calibration", () => {
  it("makes the two picked features exactly the real distance apart, the first one staying put", () => {
    const a: Pt = [12.37, 18.05];
    const b: Pt = [71.9, 22.4];
    const after = calibrate(photo, a, b, 182, "none");
    const [a2, b2] = featuresAfter(photo, after, a, b);
    expect(dist(a2, a)).toBeLessThan(TOL);
    expect(Math.abs(dist(a2, b2) - 182)).toBeLessThan(TOL);
    // uniform scale: the aspect ratio of the photo is kept
    expect(after.width_mm / after.height_mm).toBeCloseTo(100 / 75, 6);
  });

  it("works on an already rotated image, and recalibrating is exact again", () => {
    const tilted = { ...photo, rotation_deg: 17.5 };
    const a: Pt = [5, 5];
    const b: Pt = [48, 61];
    const once = calibrate(tilted, a, b, 120, "none");
    const [a2, b2] = featuresAfter(tilted, once, a, b);
    expect(Math.abs(dist(a2, b2) - 120)).toBeLessThan(TOL);
    const twice = calibrate(once, a2, b2, 121.5, "none");
    const [a3, b3] = featuresAfter(once, twice, a2, b2);
    expect(Math.abs(dist(a3, b3) - 121.5)).toBeLessThan(TOL);
  });

  it("straightens a slightly tilted photo with the smallest rotation, never upside down", () => {
    // the ruler on the photo goes right and slightly down: about +3°
    const a: Pt = [0, 0];
    const b: Pt = [100, 5.24];
    const after = calibrate(photo, a, b, 150, "horizontal");
    const [a2, b2] = featuresAfter(photo, after, a, b);
    expect(Math.abs(b2[1] - a2[1])).toBeLessThan(TOL); // now horizontal
    expect(b2[0]).toBeGreaterThan(a2[0]); // still pointing right: not rotated by 180°
    expect(after.rotation_deg).toBeCloseTo(-3, 0);
    expect(Math.abs(dist(a2, b2) - 150)).toBeLessThan(TOL);

    // a ruler shot pointing left is straightened toward the left, not flipped
    const left = calibrate(photo, [0, 0], [-100, 4], 100, "horizontal");
    const [l2, m2] = featuresAfter(photo, left, [0, 0], [-100, 4]);
    expect(m2[0]).toBeLessThan(l2[0]);
    expect(Math.abs(left.rotation_deg)).toBeLessThan(3);
  });

  it("straightens vertically", () => {
    const after = calibrate(photo, [10, 0], [12, 80], 80, "vertical");
    const [a2, b2] = featuresAfter(photo, after, [10, 0], [12, 80]);
    expect(Math.abs(b2[0] - a2[0])).toBeLessThan(TOL);
    expect(b2[1]).toBeGreaterThan(a2[1]);
  });

  it("can put the first point on the origin", () => {
    const a: Pt = [33.3, -12.1];
    const b: Pt = [80, -12.1];
    const after = calibrate(photo, a, b, 90, "horizontal", true);
    const [a2, b2] = featuresAfter(photo, after, a, b);
    expect(dist(a2, [0, 0])).toBeLessThan(TOL);
    expect(Math.abs(b2[0] - 90)).toBeLessThan(TOL);
    expect(Math.abs(b2[1])).toBeLessThan(TOL);
  });

  it("refuses degenerate input", () => {
    expect(() => calibrate(photo, [1, 1], [1, 1], 50)).toThrow();
    expect(() => calibrate(photo, [0, 0], [10, 0], 0)).toThrow();
    expect(() => calibrate(photo, [0, 0], [10, 0], Number.NaN)).toThrow();
  });
});

describe("background helpers", () => {
  it("places a new image with the photo's aspect ratio", () => {
    expect(initialPlacement(4000, 3000, [10, 20], 200)).toEqual({ cx: 10, cy: 20, width_mm: 200, height_mm: 150, rotation_deg: 0 });
  });

  it("limits the longest side to 4000 px and keeps small images untouched", () => {
    expect(fitPixels(6000, 4000)).toEqual([4000, 2667]);
    expect(fitPixels(3000, 9000)).toEqual([1333, 4000]);
    expect(fitPixels(1200, 800)).toEqual([1200, 800]);
  });

  it("reports the resolution of the calibrated photo", () => {
    // a 200 mm wide view of a 4000 px photo: 0.05 mm per pixel, fine enough for 0.1 mm work
    expect(mmPerPixel({ ...photo, width_mm: 200 }, 4000)).toBeCloseTo(0.05, 9);
    expect(mmPerPixel(photo, 0)).toBe(Infinity);
  });

  it("normalises angles to (-180, 180]", () => {
    expect([normalizeDeg(190), normalizeDeg(-190), normalizeDeg(180), normalizeDeg(-180), normalizeDeg(720)]).toEqual([-170, 170, 180, 180, 0]);
  });
});
