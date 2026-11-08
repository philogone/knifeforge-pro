/**
 * True-size display ("1:1"). Without calibration the editor assumes the CSS reference of
 * 96 px per inch, which is rarely the physical truth. The maker can calibrate once by matching
 * a bank card (ISO/IEC 7810 ID-1, 85.60 mm wide) on screen; the result is kept per
 * device-pixel ratio, since browser zoom and each monitor change it.
 */
import { PX_PER_MM_CSS } from "./constants";

export const CARD_WIDTH_MM = 85.6;
export const CARD_HEIGHT_MM = 53.98;
const KEY = "knifeforge_screen_px_per_mm";

function slot(): string {
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  return `${KEY}@${dpr.toFixed(2)}`;
}

/** CSS pixels per real millimetre on this screen (calibrated, or the 96 dpi assumption) */
export function screenPxPerMm(): number {
  try {
    const value = Number(localStorage.getItem(slot()));
    if (value > 1 && value < 20) return value;
  } catch {
    // storage blocked: fall back to the CSS reference
  }
  return PX_PER_MM_CSS;
}

export function isScreenCalibrated(): boolean {
  try {
    return Number(localStorage.getItem(slot())) > 0;
  } catch {
    return false;
  }
}

export function saveScreenCalibration(pxPerMm: number | null): void {
  try {
    if (pxPerMm === null) localStorage.removeItem(slot());
    else localStorage.setItem(slot(), String(pxPerMm));
  } catch {
    // not persisted
  }
}
