/**
 * Display unit of the editor: millimetres or inches.
 *
 * Every length is stored, computed and exported in millimetres; only what the user reads and
 * types is converted. 1 in = 25.4 mm exactly (international inch), so a value typed in inches
 * lands on the exact millimetre value: 1.875 in → 47.625 mm.
 *
 * Inches are shown to 4 decimals (0.0001 in = 0.00254 mm), millimetres to 2: both stay well
 * inside the tool's 0.1 mm precision.
 */

import { ref, watch } from "vue";

export type LengthUnit = "mm" | "in";

export const MM_PER_IN = 25.4;
const STORAGE_KEY = "knifeforge_length_unit";

/** mm → value shown in `unit`, rounded for display */
export function toDisplay(mm: number, unit: LengthUnit): number {
  if (unit === "in") return Math.round((mm / MM_PER_IN) * 1e4) / 1e4;
  return Math.round(mm * 100) / 100;
}

/** value typed in `unit` → mm, unrounded */
export function fromDisplay(value: number, unit: LengthUnit): number {
  return unit === "in" ? value * MM_PER_IN : value;
}

export function formatLength(mm: number, unit: LengthUnit): string {
  return toDisplay(mm, unit).toString();
}

/** "12.5 mm", "0.4921 in" */
export function formatLengthWithUnit(mm: number, unit: LengthUnit): string {
  return `${formatLength(mm, unit)} ${unit}`;
}

/** area: mm² shown as mm², in inches as in² (4 decimals) */
export function formatArea(mm2: number, unit: LengthUnit): string {
  if (unit === "in") return `${Math.round((mm2 / (MM_PER_IN * MM_PER_IN)) * 1e4) / 1e4} in²`;
  return `${Math.round(mm2 * 100) / 100} mm²`;
}

/** Ruler label spacing in mm for the unit: inches step in binary fractions, as on a steel rule. */
export function rulerSteps(unit: LengthUnit): number[] {
  if (unit === "in") return [1 / 64, 1 / 32, 1 / 16, 1 / 8, 1 / 4, 1 / 2, 1, 2, 5, 10, 20, 50].map((i) => i * MM_PER_IN);
  return [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
}

function readStored(): LengthUnit {
  try {
    return localStorage.getItem(STORAGE_KEY) === "in" ? "in" : "mm";
  } catch {
    return "mm";
  }
}

// one preference for the whole app, kept on this browser
const unit = ref<LengthUnit>(readStored());
watch(unit, (u) => {
  try {
    localStorage.setItem(STORAGE_KEY, u);
  } catch {
    // not persisted
  }
});

export function useLengthUnit() {
  return unit;
}
