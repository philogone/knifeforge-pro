/** Design document format — mirrors backend/app/schemas/design.py.
 *  Millimetres, y-down, Bézier handles stored relative to their anchor. */

export interface DocNode {
  x: number;
  y: number;
  ix: number;
  iy: number;
  ox: number;
  oy: number;
}

export type LayerRole = "cut" | "hole" | "engrave" | "construction" | "dimension";

export interface DocLayer {
  id: string;
  name: string;
  role: LayerRole;
  visible: boolean;
  locked: boolean;
}

export interface PathObject {
  id: string;
  type: "path";
  layer: string;
  name: string | null;
  closed: boolean;
  contours: DocNode[][];
}

export interface DimensionObject {
  id: string;
  type: "dimension";
  layer: string;
  a: [number, number];
  b: [number, number];
  offset: number;
  label: string | null;
}

export type DocObject = PathObject | DimensionObject;

export interface DesignDocument {
  version: 1;
  unit: "mm";
  layers: DocLayer[];
  objects: DocObject[];
}

export type ToolName = "select" | "node" | "pen" | "rect" | "ellipse" | "line" | "polygon" | "dimension" | "pan";

export interface Bounds {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface SelectionInfo {
  count: number;
  ids: string[];
  bounds: Bounds | null;
  name: string | null;
  layerId: string | null;
  mixedLayers: boolean;
  /** Only for a single path selection */
  path: { nodeCount: number; closed: boolean; compound: boolean; area: number; perimeter: number } | null;
  /** Only for a single dimension selection */
  dimension: { offset: number; label: string | null; length: number } | null;
  /** Node-tool state */
  selectedNodes: number;
  singleNode: { x: number; y: number; smooth: boolean } | null;
}

export interface EditorSnapshot {
  doc: DesignDocument;
}
