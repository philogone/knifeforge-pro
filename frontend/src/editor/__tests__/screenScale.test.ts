import { beforeEach, describe, expect, it } from "vitest";

import { PX_PER_MM_CSS } from "@/editor/constants";
import { CARD_WIDTH_MM, isScreenCalibrated, saveScreenCalibration, screenPxPerMm } from "@/editor/screenScale";

describe("true-size screen calibration", () => {
  beforeEach(() => localStorage.clear());

  it("assumes 96 dpi until calibrated", () => {
    expect(isScreenCalibrated()).toBe(false);
    expect(screenPxPerMm()).toBeCloseTo(PX_PER_MM_CSS, 9);
  });

  it("uses the bank-card measurement once saved, and forgets it on reset", () => {
    saveScreenCalibration(400 / CARD_WIDTH_MM); // the card measured 400 CSS px on this screen
    expect(isScreenCalibrated()).toBe(true);
    expect(screenPxPerMm() * CARD_WIDTH_MM).toBeCloseTo(400, 9);
    saveScreenCalibration(null);
    expect(screenPxPerMm()).toBeCloseTo(PX_PER_MM_CSS, 9);
  });

  it("ignores absurd stored values", () => {
    localStorage.setItem(`knifeforge_screen_px_per_mm@${(window.devicePixelRatio || 1).toFixed(2)}`, "999");
    expect(screenPxPerMm()).toBeCloseTo(PX_PER_MM_CSS, 9);
  });
});
