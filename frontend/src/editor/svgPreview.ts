import type { DesignDocument, DocNode } from "./types";

function fmt(n: number): string {
  return (Math.round(n * 1000) / 1000).toString();
}

export function contourPath(nodes: DocNode[], closed: boolean): string {
  if (!nodes.length) return "";
  let d = `M${fmt(nodes[0].x)} ${fmt(nodes[0].y)}`;
  const seg = (a: DocNode, b: DocNode) => {
    if (!a.ox && !a.oy && !b.ix && !b.iy) return `L${fmt(b.x)} ${fmt(b.y)}`;
    return `C${fmt(a.x + a.ox)} ${fmt(a.y + a.oy)} ${fmt(b.x + b.ix)} ${fmt(b.y + b.iy)} ${fmt(b.x)} ${fmt(b.y)}`;
  };
  for (let i = 0; i < nodes.length - 1; i++) d += seg(nodes[i], nodes[i + 1]);
  if (closed && nodes.length > 1) d += seg(nodes[nodes.length - 1], nodes[0]) + "Z";
  return d;
}

/** Small SVG thumbnail of a design (cut / hole / engrave layers only). */
export function documentToSvg(doc: DesignDocument, size = 160): string {
  const layers = new Map(doc.layers.map((l) => [l.id, l]));
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const parts: string[] = [];
  for (const obj of doc.objects) {
    if (obj.type !== "path") continue;
    const layer = layers.get(obj.layer);
    if (!layer || !layer.visible) continue;
    if (layer.role !== "cut" && layer.role !== "hole" && layer.role !== "engrave") continue;
    for (const c of obj.contours) {
      for (const n of c) {
        for (const [x, y] of [[n.x, n.y], [n.x + n.ox, n.y + n.oy], [n.x + n.ix, n.y + n.iy]]) {
          minX = Math.min(minX, x); maxX = Math.max(maxX, x);
          minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        }
      }
    }
    const d = obj.contours.map((c) => contourPath(c, obj.closed)).join("");
    const style =
      layer.role === "engrave"
        ? 'fill="none" stroke="#2563eb" stroke-dasharray="3 2"'
        : layer.role === "hole"
          ? 'fill="#fff" stroke="#dc2626"'
          : 'fill="#e2e8f0" stroke="#0f172a" fill-rule="evenodd"';
    parts.push(`<path d="${d}" ${style} vector-effect="non-scaling-stroke" stroke-width="1.2"/>`);
  }
  if (!parts.length || !isFinite(minX)) return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}"></svg>`;
  const pad = Math.max(maxX - minX, maxY - minY) * 0.06 + 1;
  const vb = `${fmt(minX - pad)} ${fmt(minY - pad)} ${fmt(maxX - minX + 2 * pad)} ${fmt(maxY - minY + 2 * pad)}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" preserveAspectRatio="xMidYMid meet">${parts.join("")}</svg>`;
}
