/** Reference image (photo / scan) placed under the drawing to trace a pattern from it.
 *  Pure placement maths, kept apart from Paper.js so it can be tested exactly. */

export interface BackgroundPlacement {
  /** centre of the image, document mm */
  cx: number;
  cy: number;
  width_mm: number;
  height_mm: number;
  /** degrees, clockwise on screen (y points down) */
  rotation_deg: number;
}

export interface BackgroundState extends BackgroundPlacement {
  /** data URL (JPEG / PNG / WebP) */
  image: string;
  opacity: number;
  visible: boolean;
  locked: boolean;
  calibrated: boolean;
  /** image size in pixels (not stored: read back from the decoded image) */
  pixelWidth?: number;
  pixelHeight?: number;
}

export type Straighten = "none" | "horizontal" | "vertical";
type Pt = [number, number];

const round4 = (v: number) => Math.round(v * 10000) / 10000;

/** Normalise an angle to (-180, 180]. */
export function normalizeDeg(deg: number): number {
  let a = deg % 360;
  if (a <= -180) a += 360;
  if (a > 180) a -= 360;
  return a;
}

function rotateAround(p: Pt, origin: Pt, deg: number): Pt {
  const r = (deg * Math.PI) / 180;
  const dx = p[0] - origin[0];
  const dy = p[1] - origin[1];
  return [origin[0] + dx * Math.cos(r) - dy * Math.sin(r), origin[1] + dx * Math.sin(r) + dy * Math.cos(r)];
}

/**
 * Rescale (and optionally straighten) the image so that the two clicked points `a` and `b`
 * end up exactly `realMm` apart. Point `a` stays where it is (it is the anchor), unless
 * `moveAToOrigin`, in which case the whole image is then translated so `a` lands on (0, 0).
 *
 * Straightening rotates about `a` so that a→b becomes horizontal or vertical, choosing the
 * smallest rotation (a slightly tilted photo is corrected, never flipped upside down).
 */
export function calibrate(
  bg: BackgroundPlacement,
  a: Pt,
  b: Pt,
  realMm: number,
  straighten: Straighten = "none",
  moveAToOrigin = false,
): BackgroundPlacement {
  const measured = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (!(measured > 1e-9) || !(realMm > 0) || !Number.isFinite(realMm)) {
    throw new Error("Calibration needs two distinct points and a positive real distance");
  }
  const s = realMm / measured;
  let c: Pt = [a[0] + (bg.cx - a[0]) * s, a[1] + (bg.cy - a[1]) * s];
  let rotation = bg.rotation_deg;

  if (straighten !== "none") {
    const angle = (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI;
    const targets = straighten === "horizontal" ? [0, 180, -180] : [90, -90];
    let delta = Infinity;
    for (const target of targets) {
      const d = normalizeDeg(target - angle);
      if (Math.abs(d) < Math.abs(delta)) delta = d;
    }
    c = rotateAround(c, a, delta);
    rotation = normalizeDeg(rotation + delta);
  }
  if (moveAToOrigin) c = [c[0] - a[0], c[1] - a[1]];

  return {
    cx: round4(c[0]),
    cy: round4(c[1]),
    width_mm: round4(bg.width_mm * s),
    height_mm: round4(bg.height_mm * s),
    rotation_deg: round4(rotation),
  };
}

/** Initial placement of a freshly imported image: centred on `center`, `targetWidthMm` wide. */
export function initialPlacement(pixelWidth: number, pixelHeight: number, center: Pt, targetWidthMm: number): BackgroundPlacement {
  const w = Math.max(1, targetWidthMm);
  return { cx: round4(center[0]), cy: round4(center[1]), width_mm: round4(w), height_mm: round4((w * pixelHeight) / pixelWidth), rotation_deg: 0 };
}

/** Size of one image pixel in mm: the finest detail the photo can carry once calibrated. */
export function mmPerPixel(bg: BackgroundPlacement, pixelWidth: number): number {
  return pixelWidth > 0 ? bg.width_mm / pixelWidth : Infinity;
}

/** Longest side, in pixels, kept when an image is imported (larger photos are downscaled). */
export const MAX_IMAGE_PX = 4000;
/** Above this size (characters of data URL), the original file is re-encoded even if small enough in pixels. */
const MAX_KEEP_ORIGINAL_CHARS = 6_000_000;

/** Pixel size after limiting the longest side to `max`, keeping the aspect ratio. */
export function fitPixels(width: number, height: number, max = MAX_IMAGE_PX): [number, number] {
  const longest = Math.max(width, height);
  if (longest <= max) return [width, height];
  const k = max / longest;
  return [Math.max(1, Math.round(width * k)), Math.max(1, Math.round(height * k))];
}

/**
 * Read an image file as a data URL suited for storage: JPEG / PNG / WebP only, longest side
 * ≤ MAX_IMAGE_PX. A small enough original is kept byte-for-byte (no recompression);
 * otherwise it is redrawn on a canvas (the browser applies the EXIF orientation) as JPEG.
 */
export async function loadImageFile(file: File): Promise<{ dataUrl: string; width: number; height: number }> {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) throw new Error("unsupported");
  const original = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
  const img = await decode(original);
  const [w, h] = fitPixels(img.naturalWidth, img.naturalHeight);
  if (w === img.naturalWidth && h === img.naturalHeight && original.length <= MAX_KEEP_ORIGINAL_CHARS) {
    return { dataUrl: original, width: w, height: h };
  }
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(img, 0, 0, w, h);
  return { dataUrl: canvas.toDataURL("image/jpeg", 0.92), width: w, height: h };
}

function decode(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("decode"));
    img.src = src;
  });
}
