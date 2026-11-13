import { UI_COLOR } from "./constants";
import { MM_PER_IN, rulerSteps, type LengthUnit } from "./units";

/** theme colours of the drawing surface, from the CSS variables in main.css */
function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/** Pure canvas drawing for the editor background (grid) and rulers. They are
 *  drawn on 2D canvases layered under / over the Paper.js canvas, driven by
 *  the engine's view transform, so Paper never has to redraw thousands of lines. */

export interface ViewTransform {
  /** world point (mm) at the centre of the canvas */
  centerX: number;
  centerY: number;
  /** pixels per mm */
  zoom: number;
  width: number;
  height: number;
}

export function worldToScreen(v: ViewTransform, x: number, y: number): [number, number] {
  return [(x - v.centerX) * v.zoom + v.width / 2, (y - v.centerY) * v.zoom + v.height / 2];
}

export function screenToWorld(v: ViewTransform, sx: number, sy: number): [number, number] {
  return [(sx - v.width / 2) / v.zoom + v.centerX, (sy - v.height / 2) / v.zoom + v.centerY];
}

const NICE = [1, 2, 5];

/** Smallest "nice" step (1, 2, 5 × 10^n mm) giving at least `minPx` pixels between ticks. */
export function niceStep(zoom: number, minPx: number): number {
  const minMm = minPx / zoom;
  const exp = Math.floor(Math.log10(minMm));
  for (let e = exp; e <= exp + 1; e++) {
    for (const m of NICE) {
      const step = m * 10 ** e;
      if (step >= minMm) return step;
    }
  }
  return 10 ** (exp + 1);
}

const MAJOR_FACTOR: Record<number, number> = { 1: 10, 2: 5, 5: 2 };

/**
 * Grid lines to draw for a given snap step: the snap step itself when it is at least `minPx`
 * apart on screen, else the first of 2×, 5×, 10×, 20×… that is. Major lines fall on multiples of
 * 10 snap steps (e.g. 1 mm grid → centimetre lines), so the grid you see is the grid you snap to.
 */
export function gridSteps(zoom: number, snapStep: number, minPx = 8): { minor: number; major: number } {
  for (let e = 0; e < 12; e++) {
    for (const m of NICE) {
      const minor = snapStep * m * 10 ** e;
      if (minor * zoom >= minPx) return { minor, major: minor * MAJOR_FACTOR[m] };
    }
  }
  return { minor: snapStep, major: snapStep * 10 };
}

export interface GridStyle {
  /** snap step, mm (falls back to a zoom-based step when absent) */
  step?: number;
  show?: boolean;
  dark?: boolean;
}

export function drawGrid(ctx: CanvasRenderingContext2D, v: ViewTransform, style: GridStyle = {}): void {
  const dark = !!style.dark;
  ctx.clearRect(0, 0, v.width, v.height);
  ctx.fillStyle = dark ? "#0b1220" : cssVar("--plate", "#ffffff");
  ctx.fillRect(0, 0, v.width, v.height);
  if (style.show === false) return;

  const { minor, major } = style.step ? gridSteps(v.zoom, style.step) : { minor: niceStep(v.zoom, 12), major: niceStep(v.zoom, 12) * 5 };
  const [wx0, wy0] = screenToWorld(v, 0, 0);
  const [wx1, wy1] = screenToWorld(v, v.width, v.height);

  const lines = (step: number, color: string, lineWidth: number) => {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    for (let x = Math.floor(wx0 / step) * step; x <= wx1; x += step) {
      const sx = Math.round((x - v.centerX) * v.zoom + v.width / 2) + 0.5;
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, v.height);
    }
    for (let y = Math.floor(wy0 / step) * step; y <= wy1; y += step) {
      const sy = Math.round((y - v.centerY) * v.zoom + v.height / 2) + 0.5;
      ctx.moveTo(0, sy);
      ctx.lineTo(v.width, sy);
    }
    ctx.stroke();
  };
  lines(minor, dark ? "#16213a" : cssVar("--plate-grid-minor", "#f0ede6"), 1);
  lines(major, dark ? "#24324f" : cssVar("--plate-grid-major", "#e3dfd5"), 1);

  // origin axes
  const [ox, oy] = worldToScreen(v, 0, 0);
  ctx.beginPath();
  ctx.strokeStyle = "#b0bd72";
  ctx.lineWidth = 1;
  ctx.moveTo(Math.round(ox) + 0.5, 0);
  ctx.lineTo(Math.round(ox) + 0.5, v.height);
  ctx.moveTo(0, Math.round(oy) + 0.5);
  ctx.lineTo(v.width, Math.round(oy) + 0.5);
  ctx.stroke();
}

export const RULER_SIZE = 20;

export interface RulerGuide {
  axis: "x" | "y";
  pos: number;
}

/** Ruler tick spacing (mm) for the display unit: 1-2-5 in millimetres, binary fractions in inches. */
export function rulerStep(zoom: number, minPx: number, unit: LengthUnit): number {
  if (unit === "mm") return niceStep(zoom, minPx);
  const steps = rulerSteps("in");
  return steps.find((s) => s * zoom >= minPx) ?? steps[steps.length - 1];
}

export function drawRulers(
  ctx: CanvasRenderingContext2D,
  v: ViewTransform,
  cursor: [number, number] | null,
  guides: RulerGuide[] = [],
  preview: RulerGuide | null = null,
  mirrorAxis: RulerGuide | null = null,
  unit: LengthUnit = "mm",
): void {
  ctx.clearRect(0, 0, v.width, v.height);
  // guides live on this top canvas so they stay visible over shapes and over a reference photo
  const guideLine = (g: RulerGuide, dashed: boolean) => {
    ctx.beginPath();
    ctx.strokeStyle = dashed ? "rgba(8,145,178,0.7)" : "rgba(6,182,212,0.95)";
    ctx.lineWidth = 1;
    ctx.setLineDash(dashed ? [6, 4] : []);
    if (g.axis === "x") {
      const sx = Math.round(worldToScreen(v, g.pos, 0)[0]) + 0.5;
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, v.height);
    } else {
      const sy = Math.round(worldToScreen(v, 0, g.pos)[1]) + 0.5;
      ctx.moveTo(0, sy);
      ctx.lineTo(v.width, sy);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  };
  for (const g of guides) guideLine(g, false);
  if (preview) guideLine(preview, true);
  if (mirrorAxis) {
    // magenta, dash-dot: the symmetry axis, distinct from guides
    ctx.beginPath();
    ctx.strokeStyle = "rgba(192,38,211,0.85)";
    ctx.setLineDash([10, 3, 2, 3]);
    if (mirrorAxis.axis === "x") {
      const sx = Math.round(worldToScreen(v, mirrorAxis.pos, 0)[0]) + 0.5;
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, v.height);
    } else {
      const sy = Math.round(worldToScreen(v, 0, mirrorAxis.pos)[1]) + 0.5;
      ctx.moveTo(0, sy);
      ctx.lineTo(v.width, sy);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.fillStyle = cssVar("--ruler-bg", "#f8f6f1");
  ctx.fillRect(0, 0, v.width, RULER_SIZE);
  ctx.fillRect(0, 0, RULER_SIZE, v.height);
  ctx.strokeStyle = cssVar("--ruler-line", "#cdc7ba");
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, v.width - 1, RULER_SIZE);
  ctx.strokeRect(0.5, 0.5, RULER_SIZE, v.height - 1);

  ctx.fillStyle = cssVar("--ruler-text", "#57534b");
  ctx.font = "10px \"IBM Plex Mono\", ui-monospace, monospace";
  const minor = rulerStep(v.zoom, 8, unit);
  const label = rulerStep(v.zoom, 60, unit);
  const [wx0, wy0] = screenToWorld(v, 0, 0);
  const [wx1, wy1] = screenToWorld(v, v.width, v.height);

  ctx.beginPath();
  ctx.strokeStyle = cssVar("--ruler-tick", "#a39d90");
  for (let x = Math.floor(wx0 / minor) * minor; x <= wx1; x += minor) {
    const sx = Math.round((x - v.centerX) * v.zoom + v.width / 2) + 0.5;
    const isLabel = Math.abs(x / label - Math.round(x / label)) < 1e-6;
    ctx.moveTo(sx, RULER_SIZE);
    ctx.lineTo(sx, RULER_SIZE - (isLabel ? 10 : 4));
    if (isLabel) ctx.fillText(formatTick(x, unit), sx + 2, 9);
  }
  for (let y = Math.floor(wy0 / minor) * minor; y <= wy1; y += minor) {
    const sy = Math.round((y - v.centerY) * v.zoom + v.height / 2) + 0.5;
    const isLabel = Math.abs(y / label - Math.round(y / label)) < 1e-6;
    ctx.moveTo(RULER_SIZE, sy);
    ctx.lineTo(RULER_SIZE - (isLabel ? 10 : 4), sy);
    if (isLabel) {
      ctx.save();
      ctx.translate(9, sy - 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(formatTick(y, unit), 0, 0);
      ctx.restore();
    }
  }
  ctx.stroke();

  if (cursor) {
    const [cx, cy] = worldToScreen(v, cursor[0], cursor[1]);
    ctx.fillStyle = UI_COLOR;
    ctx.fillRect(Math.round(cx), 0, 1, RULER_SIZE);
    ctx.fillRect(0, Math.round(cy), RULER_SIZE, 1);
  }
  ctx.fillStyle = cssVar("--ruler-corner", "#e3dfd5");
  ctx.fillRect(0, 0, RULER_SIZE, RULER_SIZE);
  ctx.fillStyle = cssVar("--ruler-corner-text", "#6f6a60");
  ctx.fillText(unit, 2, 13);
}

function formatTick(value: number, unit: LengthUnit): string {
  if (unit === "in") return String(Math.round((value / MM_PER_IN) * 1e4) / 1e4);
  const rounded = Math.round(value * 1000) / 1000;
  return String(rounded);
}
