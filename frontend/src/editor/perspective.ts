/** Perspective correction of the reference photo: four clicked corners of a known rectangle
 *  (a sheet of paper, a square, a card…) give the plane-to-plane homography; the photo is then
 *  resampled so that one pixel is the same size everywhere and the rectangle is exactly W × H mm.
 *
 *  Only the plane of the rectangle is corrected: the part must lie flat in that same plane
 *  (anything thicker sits closer to the lens and is enlarged). Lens distortion is not corrected.
 *  Pure maths, apart from `rectifyImage`, so the geometry can be checked exactly. */

import type { BackgroundPlacement } from "./background";

export type Pt = [number, number];
/** 3 × 3 matrix, row-major */
export type Mat3 = [number, number, number, number, number, number, number, number, number];

export function applyHomography(h: Mat3, p: Pt): Pt | null {
  const w = h[6] * p[0] + h[7] * p[1] + h[8];
  if (Math.abs(w) < 1e-12) return null;
  return [(h[0] * p[0] + h[1] * p[1] + h[2]) / w, (h[3] * p[0] + h[4] * p[1] + h[5]) / w];
}

/** Hartley normalisation: centroid at 0, mean distance √2. Returns the matrix doing it. */
function normalizer(pts: Pt[]): Mat3 {
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const mean = pts.reduce((s, p) => s + Math.hypot(p[0] - cx, p[1] - cy), 0) / pts.length;
  const k = mean > 0 ? Math.SQRT2 / mean : 1;
  return [k, 0, -k * cx, 0, k, -k * cy, 0, 0, 1];
}

function mul3(a: Mat3, b: Mat3): Mat3 {
  const out = new Array(9).fill(0) as Mat3;
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) for (let i = 0; i < 3; i++) out[r * 3 + c] += a[r * 3 + i] * b[i * 3 + c];
  return out;
}

export function invert3(m: Mat3): Mat3 | null {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h;
  const B = -(d * i - f * g);
  const C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-300) return null;
  const k = 1 / det;
  return [A * k, -(b * i - c * h) * k, (b * f - c * e) * k, B * k, (a * i - c * g) * k, -(a * f - c * d) * k, C * k, -(a * h - b * g) * k, (a * e - b * d) * k];
}

/** Solve A·x = b (n × n) by Gaussian elimination with partial pivoting; null when singular. */
function solve(A: number[][], b: number[]): number[] | null {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(M[r][col]) > Math.abs(M[pivot][col])) pivot = r;
    if (Math.abs(M[pivot][col]) < 1e-12) return null;
    [M[col], M[pivot]] = [M[pivot], M[col]];
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const f = M[r][col] / M[col][col];
      if (f) for (let c = col; c <= n; c++) M[r][c] -= f * M[col][c];
    }
  }
  return M.map((row, i) => row[n] / row[i]);
}

/** Homography mapping the four `src` points exactly onto the four `dst` points (null if degenerate). */
export function solveHomography(src: Pt[], dst: Pt[]): Mat3 | null {
  if (src.length !== 4 || dst.length !== 4) return null;
  const ns = normalizer(src);
  const nd = normalizer(dst);
  const s = src.map((p) => applyHomography(ns, p)!);
  const d = dst.map((p) => applyHomography(nd, p)!);
  const A: number[][] = [];
  const b: number[] = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = s[i];
    const [u, v] = d[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]);
    b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]);
    b.push(v);
  }
  const x = solve(A, b);
  if (!x) return null;
  const hn: Mat3 = [x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], 1];
  const ndInv = invert3(nd);
  if (!ndInv) return null;
  const h = mul3(ndInv, mul3(hn, ns));
  return h.map((v) => v / h[8]) as Mat3;
}

const cross = (o: Pt, a: Pt, b: Pt) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

/** Twice the signed area (shoelace); positive = clockwise on screen (y down). */
export function signedArea2(q: Pt[]): number {
  let s = 0;
  for (let i = 0; i < q.length; i++) {
    const a = q[i];
    const b = q[(i + 1) % q.length];
    s += a[0] * b[1] - b[0] * a[1];
  }
  return s;
}

/** The four points, in click order, form a convex quadrilateral (no crossing, no three aligned). */
export function isConvexQuad(q: Pt[]): boolean {
  if (q.length !== 4) return false;
  const area = Math.abs(signedArea2(q));
  const size = Math.max(...q.map((p, i) => Math.hypot(p[0] - q[(i + 1) % 4][0], p[1] - q[(i + 1) % 4][1])));
  if (!(size > 0) || area < 1e-6 * size * size) return false;
  const signs = q.map((_, i) => Math.sign(cross(q[i], q[(i + 1) % 4], q[(i + 2) % 4])));
  return signs.every((s) => s !== 0 && s === signs[0]);
}

/**
 * Where the four clicked corners go once corrected, relative to the first one (mm, y down).
 * Corner 1→2 is a side `width` long, 2→3 a side `height` long. The first side keeps its on-screen
 * direction rounded to the nearest quarter turn, and the rectangle keeps the clicks' turning
 * direction, so the photo is never mirrored whichever way round the corners were clicked.
 */
export function rectangleTargets(clicked: Pt[], width: number, height: number): Pt[] {
  const [p0, p1] = clicked;
  const quarter = Math.round(Math.atan2(p1[1] - p0[1], p1[0] - p0[0]) / (Math.PI / 2));
  const e1: Pt = [Math.round(Math.cos((quarter * Math.PI) / 2)), Math.round(Math.sin((quarter * Math.PI) / 2))];
  // clockwise on screen (y down): rotate e1 by +90°, i.e. (x, y) → (−y, x)
  const e2: Pt = signedArea2(clicked) > 0 ? [-e1[1], e1[0]] : [e1[1], -e1[0]];
  const at = (a: number, b: number): Pt => [a * width * e1[0] + b * height * e2[0] + 0, a * width * e1[1] + b * height * e2[1] + 0];
  return [at(0, 0), at(1, 0), at(1, 1), at(0, 1)];
}

/** Document point (mm) → pixel coordinates of the image placed as `bg` (pixel i spans [i, i+1]). */
export function docToPixel(bg: BackgroundPlacement, pixelWidth: number, pixelHeight: number, p: Pt): Pt {
  const r = (-bg.rotation_deg * Math.PI) / 180;
  const dx = p[0] - bg.cx;
  const dy = p[1] - bg.cy;
  const lx = dx * Math.cos(r) - dy * Math.sin(r);
  const ly = dx * Math.sin(r) + dy * Math.cos(r);
  return [(lx * pixelWidth) / bg.width_mm + pixelWidth / 2, (ly * pixelHeight) / bg.height_mm + pixelHeight / 2];
}

export interface RectifyPlan {
  /** corrected mm (relative to corner 1) → source pixel, for resampling */
  toSource: Mat3;
  /** area of the corrected image, mm relative to corner 1 */
  minX: number;
  minY: number;
  /** output size in pixels, and pixels per mm (the same in x and y) */
  outWidth: number;
  outHeight: number;
  pxPerMm: number;
  /** coarsest detail the photo carries inside the rectangle: mm per source pixel, worst side */
  sourceMmPerPx: number;
}

export interface RectifyOptions {
  /** longest output side, pixels */
  maxPx?: number;
  /** most output pixels in all */
  maxPixels?: number;
  /** how far around the rectangle the corrected image may extend, in multiples of its longest
   *  side (at least 100 mm): a small reference such as a card may sit beside a long blade */
  margin?: number;
}

/**
 * Plan the correction: `pixels` = the four corners in source pixel coordinates (click order),
 * `targets` = where they go (mm). The output resolution matches the sharpest side of the
 * rectangle on the photo (no detail lost where the photo is closest), capped by `maxPx`.
 * The output covers the photo, clipped to `margin` × the rectangle's longest side around it:
 * far from it, towards the horizon, the photo would stretch without limit.
 */
export function planRectify(pixels: Pt[], targets: Pt[], pixelWidth: number, pixelHeight: number, options: RectifyOptions = {}): RectifyPlan | null {
  const { maxPx = 4000, maxPixels = 16_000_000, margin = 1.5 } = options;
  if (!isConvexQuad(pixels) || !isConvexQuad(targets)) return null;
  const toRect = solveHomography(pixels, targets);
  const toSource = toRect && invert3(toRect);
  if (!toRect || !toSource) return null;

  let finest = 0;
  let coarsest = Infinity;
  for (let i = 0; i < 4; i++) {
    const j = (i + 1) % 4;
    const px = Math.hypot(pixels[j][0] - pixels[i][0], pixels[j][1] - pixels[i][1]);
    const mm = Math.hypot(targets[j][0] - targets[i][0], targets[j][1] - targets[i][1]);
    finest = Math.max(finest, px / mm);
    coarsest = Math.min(coarsest, px / mm);
  }

  const tx = targets.map((t) => t[0]);
  const ty = targets.map((t) => t[1]);
  const rw = Math.max(...tx) - Math.min(...tx);
  const rh = Math.max(...ty) - Math.min(...ty);
  const extent = margin * Math.max(rw, rh, 100);
  let minX = Math.min(...tx) - extent;
  let maxX = Math.max(...tx) + extent;
  let minY = Math.min(...ty) - extent;
  let maxY = Math.max(...ty) + extent;
  // the photo's own corners, when all of them are in front of the camera, may cut that down
  const sign = Math.sign(toRect[6] * pixels[0][0] + toRect[7] * pixels[0][1] + toRect[8]);
  const corners: Pt[] = [[0, 0], [pixelWidth, 0], [pixelWidth, pixelHeight], [0, pixelHeight]];
  const inFront = corners.every((c) => Math.sign(toRect[6] * c[0] + toRect[7] * c[1] + toRect[8]) === sign);
  if (inFront) {
    const mapped = corners.map((c) => applyHomography(toRect, c)!);
    minX = Math.max(minX, Math.min(...mapped.map((p) => p[0])));
    maxX = Math.min(maxX, Math.max(...mapped.map((p) => p[0])));
    minY = Math.max(minY, Math.min(...mapped.map((p) => p[1])));
    maxY = Math.min(maxY, Math.max(...mapped.map((p) => p[1])));
  }
  const w = maxX - minX;
  const h = maxY - minY;
  if (!(w > 0 && h > 0)) return null;

  let pxPerMm = finest;
  pxPerMm = Math.min(pxPerMm, maxPx / Math.max(w, h), Math.sqrt(maxPixels / (w * h)));
  return {
    toSource,
    minX,
    minY,
    outWidth: Math.max(1, Math.round(w * pxPerMm)),
    outHeight: Math.max(1, Math.round(h * pxPerMm)),
    pxPerMm,
    sourceMmPerPx: 1 / coarsest,
  };
}

export interface Pixels {
  data: Uint8ClampedArray<ArrayBuffer>;
  width: number;
  height: number;
}

/** Resample the source through the plan (bilinear); outside the photo stays transparent. */
export function warpPixels(src: Pixels, plan: RectifyPlan): Pixels {
  const { outWidth: W, outHeight: H, toSource: m, pxPerMm, minX, minY } = plan;
  const out = new Uint8ClampedArray(new ArrayBuffer(W * H * 4));
  const sw = src.width;
  const sh = src.height;
  const s = src.data;
  for (let j = 0; j < H; j++) {
    const y = minY + (j + 0.5) / pxPerMm;
    for (let i = 0; i < W; i++) {
      const x = minX + (i + 0.5) / pxPerMm;
      const w = m[6] * x + m[7] * y + m[8];
      // pixel centres sit at i + 0.5: shift to sample indices
      const u = (m[0] * x + m[1] * y + m[2]) / w - 0.5;
      const v = (m[3] * x + m[4] * y + m[5]) / w - 0.5;
      if (!(u > -0.5 && v > -0.5 && u < sw - 0.5 && v < sh - 0.5)) continue;
      const x0 = Math.max(0, Math.min(sw - 1, Math.floor(u)));
      const y0 = Math.max(0, Math.min(sh - 1, Math.floor(v)));
      const x1 = Math.min(sw - 1, x0 + 1);
      const y1 = Math.min(sh - 1, y0 + 1);
      const fx = Math.max(0, Math.min(1, u - x0));
      const fy = Math.max(0, Math.min(1, v - y0));
      const o = (j * W + i) * 4;
      for (let c = 0; c < 4; c++) {
        const top = s[(y0 * sw + x0) * 4 + c] * (1 - fx) + s[(y0 * sw + x1) * 4 + c] * fx;
        const bottom = s[(y1 * sw + x0) * 4 + c] * (1 - fx) + s[(y1 * sw + x1) * 4 + c] * fx;
        out[o + c] = top * (1 - fy) + bottom * fy;
      }
    }
  }
  return { data: out, width: W, height: H };
}

/** Placement of the corrected image: corner 1 lands on `anchor` (mm), no rotation. */
export function rectifiedPlacement(plan: RectifyPlan, anchor: Pt): BackgroundPlacement {
  const round4 = (v: number) => Math.round(v * 10000) / 10000;
  const w = plan.outWidth / plan.pxPerMm;
  const h = plan.outHeight / plan.pxPerMm;
  return { cx: round4(anchor[0] + plan.minX + w / 2), cy: round4(anchor[1] + plan.minY + h / 2), width_mm: round4(w), height_mm: round4(h), rotation_deg: 0 };
}

/** Longest data URL kept (the server accepts 12 000 000 characters). */
const MAX_DATA_URL = 11_500_000;

/** Decode the photo, resample it through the plan and re-encode it (WebP keeps the transparent surround). */
export async function rectifyImage(dataUrl: string, plan: RectifyPlan): Promise<string> {
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error("decode"));
    el.src = dataUrl;
  });
  const source = document.createElement("canvas");
  source.width = img.naturalWidth;
  source.height = img.naturalHeight;
  const sctx = source.getContext("2d");
  if (!sctx) throw new Error("canvas");
  sctx.drawImage(img, 0, 0);
  const warped = warpPixels(sctx.getImageData(0, 0, source.width, source.height), plan);
  const out = document.createElement("canvas");
  out.width = warped.width;
  out.height = warped.height;
  const octx = out.getContext("2d");
  if (!octx) throw new Error("canvas");
  octx.putImageData(new ImageData(warped.data, warped.width, warped.height), 0, 0);
  const webp = out.toDataURL("image/webp", 0.9);
  if (webp.startsWith("data:image/webp") && webp.length <= MAX_DATA_URL) return webp;
  // no WebP encoder (Safari) or too big: JPEG on white
  const flat = document.createElement("canvas");
  flat.width = out.width;
  flat.height = out.height;
  const fctx = flat.getContext("2d");
  if (!fctx) throw new Error("canvas");
  fctx.fillStyle = "#ffffff";
  fctx.fillRect(0, 0, flat.width, flat.height);
  fctx.drawImage(out, 0, 0);
  for (const quality of [0.92, 0.8, 0.65]) {
    const jpeg = flat.toDataURL("image/jpeg", quality);
    if (jpeg.length <= MAX_DATA_URL) return jpeg;
  }
  throw new Error("tooLarge");
}
