/** Text → outlines, for engraving marks (maker's mark, logo text, serial…). The glyphs come from a
 *  font file (bundled Inter, or the user's own TTF / OTF / WOFF) through opentype.js and become
 *  ordinary editable contours: no font is needed later to export or cut them. */

import type { Font, PathCommand } from "opentype.js";

import type { DocNode } from "./types";

const round4 = (v: number) => Math.round(v * 10000) / 10000;

/**
 * Path commands (already in document mm, y down) → closed contours. Quadratic segments are
 * converted to the exactly equivalent cubic (control points at 2/3 toward the quadratic one).
 */
export function commandsToContours(commands: PathCommand[]): DocNode[][] {
  const contours: DocNode[][] = [];
  let current: DocNode[] = [];
  const last = () => current[current.length - 1];
  const close = () => {
    if (current.length > 1) {
      const a = current[0];
      const z = last();
      // the closing point usually repeats the start: merge it, keeping its incoming handle
      if (Math.abs(a.x - z.x) < 1e-6 && Math.abs(a.y - z.y) < 1e-6) {
        a.ix = z.ix;
        a.iy = z.iy;
        current.pop();
      }
    }
    if (current.length >= 3) contours.push(current);
    current = [];
  };
  for (const c of commands) {
    if (c.type === "M") {
      if (current.length) close();
      current.push({ x: round4(c.x), y: round4(c.y), ix: 0, iy: 0, ox: 0, oy: 0 });
    } else if (c.type === "L") {
      current.push({ x: round4(c.x), y: round4(c.y), ix: 0, iy: 0, ox: 0, oy: 0 });
    } else if (c.type === "C" || c.type === "Q") {
      const p0 = last();
      if (!p0) continue;
      const [c1x, c1y, c2x, c2y] =
        c.type === "C"
          ? [c.x1, c.y1, c.x2, c.y2]
          : [p0.x + (2 / 3) * (c.x1 - p0.x), p0.y + (2 / 3) * (c.y1 - p0.y), c.x + (2 / 3) * (c.x1 - c.x), c.y + (2 / 3) * (c.y1 - c.y)];
      p0.ox = round4(c1x - p0.x);
      p0.oy = round4(c1y - p0.y);
      current.push({ x: round4(c.x), y: round4(c.y), ix: round4(c2x - c.x), iy: round4(c2y - c.y), ox: 0, oy: 0 });
    } else if (c.type === "Z") {
      close();
    }
  }
  if (current.length) close();
  return contours;
}

export interface TextOptions {
  /** start of the baseline, document mm */
  x: number;
  y: number;
  /** height of the capital letters, mm (what a maker measures on the blade) */
  capHeight: number;
  /** extra space between letters, mm */
  letterSpacing?: number;
}

/** Height of capitals in font units (OS/2 table, or the height of "H" when the font lacks it). */
export function fontCapHeight(font: Font): number {
  const os2 = (font.tables as { os2?: { sCapHeight?: number } }).os2;
  if (os2?.sCapHeight) return os2.sCapHeight;
  const box = font.charToGlyph("H").getBoundingBox();
  return box.y2 - box.y1 || font.unitsPerEm * 0.7;
}

/** Characters the font cannot draw (they would come out as empty boxes). */
export function missingGlyphs(font: Font, text: string): string[] {
  return [...new Set([...text].filter((ch) => ch.trim() && font.charToGlyphIndex(ch) === 0))];
}

export function textContours(font: Font, text: string, o: TextOptions): DocNode[][] {
  const fontSize = (o.capHeight * font.unitsPerEm) / fontCapHeight(font);
  const tracking = ((o.letterSpacing ?? 0) / fontSize); // opentype.js letterSpacing is in em
  const path = font.getPath(text, o.x, o.y, fontSize, { kerning: true, letterSpacing: tracking });
  return commandsToContours(path.commands);
}

export const BUNDLED_FONTS = {
  regular: () => import("@fontsource/inter/files/inter-latin-400-normal.woff?url").then((m) => m.default as string),
  bold: () => import("@fontsource/inter/files/inter-latin-700-normal.woff?url").then((m) => m.default as string),
};

/** Parse a font from a URL or file bytes. WOFF2 is not supported by opentype.js. */
export async function loadFont(source: string | ArrayBuffer): Promise<Font> {
  const opentype = await import("opentype.js");
  const bytes = typeof source === "string" ? await (await fetch(source)).arrayBuffer() : source;
  return opentype.parse(bytes);
}
