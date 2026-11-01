import type { DocLayer, LayerRole } from "./types";

export const MM_PER_INCH = 25.4;
/** CSS reference pixel: 96 px per inch */
export const PX_PER_MM_CSS = 96 / MM_PER_INCH;

export const ROLE_STYLE: Record<LayerRole, { stroke: string; fill: string | null; dash: number[] | null; width: number }> = {
  cut: { stroke: "#0f172a", fill: "rgba(99,102,241,0.14)", dash: null, width: 1.4 },
  hole: { stroke: "#dc2626", fill: "rgba(255,255,255,0.92)", dash: null, width: 1.4 },
  engrave: { stroke: "#2563eb", fill: null, dash: null, width: 1.2 },
  construction: { stroke: "#94a3b8", fill: null, dash: [4, 4], width: 1 },
  dimension: { stroke: "#334155", fill: null, dash: null, width: 1 },
};

export const UI_COLOR = "#4f46e5";

export function defaultLayers(): DocLayer[] {
  return [
    { id: "cut", name: "Découpe", role: "cut", visible: true, locked: false },
    { id: "holes", name: "Perçages", role: "hole", visible: true, locked: false },
    { id: "engrave", name: "Gravure", role: "engrave", visible: true, locked: false },
    { id: "construction", name: "Construction", role: "construction", visible: true, locked: false },
    { id: "dimensions", name: "Cotes", role: "dimension", visible: true, locked: false },
  ];
}

export const GRID_SIZES_MM = [0.1, 0.5, 1, 2, 5, 10, 25];
export const MIN_ZOOM = 0.05; // px per mm
export const MAX_ZOOM = 400;
export const HISTORY_LIMIT = 100;
