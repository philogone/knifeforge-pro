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

export function drawGrid(ctx: CanvasRenderingContext2D, v: ViewTransform, dark = false): void {
  ctx.clearRect(0, 0, v.width, v.height);
  ctx.fillStyle = dark ? "#0b1220" : "#ffffff";
  ctx.fillRect(0, 0, v.width, v.height);

  const minor = niceStep(v.zoom, 12);
  const major = minor * 5;
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
  lines(minor, dark ? "#16213a" : "#f1f5f9", 1);
  lines(major, dark ? "#24324f" : "#e2e8f0", 1);

  // origin axes
  const [ox, oy] = worldToScreen(v, 0, 0);
  ctx.beginPath();
  ctx.strokeStyle = "#a5b4fc";
  ctx.lineWidth = 1;
  ctx.moveTo(Math.round(ox) + 0.5, 0);
  ctx.lineTo(Math.round(ox) + 0.5, v.height);
  ctx.moveTo(0, Math.round(oy) + 0.5);
  ctx.lineTo(v.width, Math.round(oy) + 0.5);
  ctx.stroke();
}

export const RULER_SIZE = 20;

export function drawRulers(ctx: CanvasRenderingContext2D, v: ViewTransform, cursor: [number, number] | null): void {
  ctx.clearRect(0, 0, v.width, v.height);
  ctx.fillStyle = "rgba(248,250,252,0.96)";
  ctx.fillRect(0, 0, v.width, RULER_SIZE);
  ctx.fillRect(0, 0, RULER_SIZE, v.height);
  ctx.strokeStyle = "#cbd5e1";
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, v.width - 1, RULER_SIZE);
  ctx.strokeRect(0.5, 0.5, RULER_SIZE, v.height - 1);

  ctx.fillStyle = "#475569";
  ctx.font = "10px sans-serif";
  const minor = niceStep(v.zoom, 8);
  const label = niceStep(v.zoom, 60);
  const [wx0, wy0] = screenToWorld(v, 0, 0);
  const [wx1, wy1] = screenToWorld(v, v.width, v.height);

  ctx.beginPath();
  ctx.strokeStyle = "#94a3b8";
  for (let x = Math.floor(wx0 / minor) * minor; x <= wx1; x += minor) {
    const sx = Math.round((x - v.centerX) * v.zoom + v.width / 2) + 0.5;
    const isLabel = Math.abs(x / label - Math.round(x / label)) < 1e-6;
    ctx.moveTo(sx, RULER_SIZE);
    ctx.lineTo(sx, RULER_SIZE - (isLabel ? 10 : 4));
    if (isLabel) ctx.fillText(formatTick(x), sx + 2, 9);
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
      ctx.fillText(formatTick(y), 0, 0);
      ctx.restore();
    }
  }
  ctx.stroke();

  if (cursor) {
    const [cx, cy] = worldToScreen(v, cursor[0], cursor[1]);
    ctx.fillStyle = "#4f46e5";
    ctx.fillRect(Math.round(cx), 0, 1, RULER_SIZE);
    ctx.fillRect(0, Math.round(cy), RULER_SIZE, 1);
  }
  ctx.fillStyle = "#e2e8f0";
  ctx.fillRect(0, 0, RULER_SIZE, RULER_SIZE);
  ctx.fillStyle = "#64748b";
  ctx.fillText("mm", 2, 13);
}

function formatTick(value: number): string {
  const rounded = Math.round(value * 1000) / 1000;
  return String(rounded);
}
