import { describe, expect, it } from "vitest";

import { rulerStep } from "@/editor/view";
import { MM_PER_IN, formatArea, formatLengthWithUnit, fromDisplay, rulerSteps, toDisplay } from "@/editor/units";

describe("length units", () => {
  it("converts typed inches to the exact millimetre value", () => {
    expect(fromDisplay(1.875, "in")).toBeCloseTo(47.625, 12);
    expect(fromDisplay(0.25, "in")).toBe(6.35);
    expect(fromDisplay(12.5, "mm")).toBe(12.5);
  });

  it("rounds for display without losing the 0.1 mm precision", () => {
    // every displayed inch value maps back within 0.0013 mm (half of 0.0001 in)
    for (const mm of [0.1, 3.175, 47.625, 123.4, 999.99]) {
      const back = fromDisplay(toDisplay(mm, "in"), "in");
      expect(Math.abs(back - mm)).toBeLessThan(0.0013);
    }
    expect(toDisplay(47.625, "in")).toBe(1.875);
    expect(toDisplay(17.6, "mm")).toBe(17.6);
  });

  it("writes lengths and areas with their unit", () => {
    expect(formatLengthWithUnit(25.4, "in")).toBe("1 in");
    expect(formatLengthWithUnit(12.345, "mm")).toBe("12.35 mm");
    expect(formatArea(MM_PER_IN * MM_PER_IN, "in")).toBe("1 in²");
    expect(formatArea(2171.84, "mm")).toBe("2171.84 mm²");
  });

  it("steps inch rulers in binary fractions, like a steel rule", () => {
    const steps = rulerSteps("in").map((s) => s / MM_PER_IN);
    expect(steps.slice(0, 4)).toEqual([1 / 64, 1 / 32, 1 / 16, 1 / 8]);
    // at 4 px/mm, ticks at least 8 px apart: 1/16 in = 1.5875 mm = 6.35 px is too close, 1/8 in fits
    expect(rulerStep(4, 8, "in")).toBeCloseTo(MM_PER_IN / 8, 12);
    expect(rulerStep(4, 8, "mm")).toBe(2);
  });
});
