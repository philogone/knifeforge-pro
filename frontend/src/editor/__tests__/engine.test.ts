import paper from "paper";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { EditorEngine, detectSvgScaleToMm } from "../engine";
import type { DesignDocument, DocNode, PathObject } from "../types";

const node = (x: number, y: number, ix = 0, iy = 0, ox = 0, oy = 0): DocNode => ({ x, y, ix, iy, ox, oy });
const K = 0.5522847498;

function rectNodes(x: number, y: number, w: number, h: number): DocNode[] {
  return [node(x, y), node(x + w, y), node(x + w, y + h), node(x, y + h)];
}

function circleNodes(cx: number, cy: number, r: number): DocNode[] {
  const k = Math.round(K * r * 1e4) / 1e4; // already at the document's 4-decimal precision
  return [node(cx + r, cy, 0, -k, 0, k), node(cx, cy + r, k, 0, -k, 0), node(cx - r, cy, 0, k, 0, -k), node(cx, cy - r, -k, 0, k, 0)];
}

function pathObj(id: string, layer: string, contours: DocNode[][], closed = true, name: string | null = null): PathObject {
  return { id, type: "path", layer, name, closed, contours };
}

const LAYERS: DesignDocument["layers"] = [
  { id: "cut", name: "Découpe", role: "cut", visible: true, locked: false },
  { id: "holes", name: "Perçages", role: "hole", visible: true, locked: false },
  { id: "dimensions", name: "Cotes", role: "dimension", visible: true, locked: false },
];

function doc(objects: DesignDocument["objects"]): DesignDocument {
  return { version: 1, unit: "mm", layers: LAYERS.map((l) => ({ ...l })), objects };
}

let engine: EditorEngine;

beforeEach(() => {
  const canvas = document.createElement("canvas");
  canvas.width = 800;
  canvas.height = 600;
  engine = new EditorEngine(canvas, { headless: true });
});

afterEach(() => engine.destroy());

const area = (id: string) => engine.evenOddArea(engine.itemById(id)!);

describe("document round trip", () => {
  it("exports exactly what it loaded, Bézier handles and compound holes included", () => {
    const source = doc([
      // export order is layer by layer (as in the layer panel), then z-order within a layer
      pathObj("plate", "cut", [rectNodes(0, 0, 100, 20), circleNodes(50, 10, 4)], true, "Plaquette"),
      pathObj("scratch", "cut", [[node(0, 30), node(20, 35, -3, 0, 4, 1)]], false),
      pathObj("pin", "holes", [circleNodes(10, 10, 2.5)]),
    ]);
    engine.loadDocument(source);
    expect(engine.exportDocument()).toEqual(source);
  });

  it("keeps layers and the objects' layer assignment", () => {
    engine.loadDocument(doc([pathObj("a", "holes", [rectNodes(0, 0, 5, 5)])]));
    expect(engine.itemById("a")!.layer.data.layerId).toBe("holes");
    expect(engine.exportDocument().layers.map((l) => l.id)).toEqual(["cut", "holes", "dimensions"]);
  });

  it("evenodd area subtracts inner contours", () => {
    engine.loadDocument(doc([pathObj("ring", "cut", [rectNodes(0, 0, 30, 30), rectNodes(10, 10, 10, 10)])]));
    expect(area("ring")).toBeCloseTo(800, 3);
  });
});

describe("history", () => {
  it("undo and redo restore documents and selection", () => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 10, 10)])]));
    engine.selectById(["a"]);
    engine.setSelectionBounds({ x: 50 });
    expect(engine.itemById("a")!.bounds.x).toBeCloseTo(50);
    expect(engine.canUndo).toBe(true);
    engine.undo();
    expect(engine.itemById("a")!.bounds.x).toBeCloseTo(0);
    expect(engine.selection.map((i) => i.data.id)).toEqual(["a"]);
    engine.redo();
    expect(engine.itemById("a")!.bounds.x).toBeCloseTo(50);
    expect(engine.canRedo).toBe(false);
  });

  it("tracks the dirty flag against the last save", () => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 10, 10)])]));
    expect(engine.dirty).toBe(false);
    engine.selectById(["a"]);
    engine.deleteSelection();
    expect(engine.dirty).toBe(true);
    engine.undo();
    expect(engine.dirty).toBe(false);
    engine.deleteSelection();
    engine.markSaved();
    expect(engine.dirty).toBe(false);
  });
});

describe("transforms", () => {
  beforeEach(() => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 40, 10)]), pathObj("b", "cut", [rectNodes(100, 50, 20, 30)])]));
  });

  it("sets exact size and position in mm", () => {
    engine.selectById(["a"]);
    engine.setSelectionBounds({ x: 5, y: 7, w: 80, h: 20 });
    const b = engine.itemById("a")!.bounds;
    expect([b.x, b.y, b.width, b.height].map((v) => Math.round(v * 1000) / 1000)).toEqual([5, 7, 80, 20]);
  });

  it("rotates 90° (swapping width and height) and flips", () => {
    engine.selectById(["a"]);
    engine.rotateSelection(90);
    const b = engine.itemById("a")!.bounds;
    expect(b.width).toBeCloseTo(10);
    expect(b.height).toBeCloseTo(40);
    const centerBefore = b.center.clone();
    engine.flipSelection("h");
    expect(engine.itemById("a")!.bounds.center.x).toBeCloseTo(centerBefore.x);
  });

  it("aligns and distributes", () => {
    engine.loadDocument(
      doc([
        pathObj("a", "cut", [rectNodes(0, 0, 10, 10)]),
        pathObj("b", "cut", [rectNodes(15, 20, 10, 10)]),
        pathObj("c", "cut", [rectNodes(100, 5, 10, 10)]),
      ]),
    );
    engine.selectAll();
    engine.distribute("h");
    expect(engine.itemById("b")!.bounds.x).toBeCloseTo(50);
    engine.align("top");
    for (const id of ["a", "b", "c"]) expect(engine.itemById(id)!.bounds.y).toBeCloseTo(0);
  });

  it("duplicates, copies and pastes with fresh ids", () => {
    engine.selectById(["a"]);
    engine.duplicateSelection();
    engine.copySelection();
    engine.pasteClipboard();
    const ids = engine.docItems().map((i) => i.data.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.length).toBe(4);
  });

  it("mirror copy doubles the selection symmetrically", () => {
    engine.selectById(["a"]);
    engine.mirrorCopy("h");
    expect(engine.docItems().length).toBe(3);
    const bounds = engine.selectionBounds()!;
    expect(bounds.width).toBeCloseTo(80);
  });
});

describe("boolean operations", () => {
  const two = () =>
    engine.loadDocument(doc([pathObj("base", "cut", [rectNodes(0, 0, 20, 20)]), pathObj("top", "cut", [rectNodes(10, 10, 20, 20)])]));

  it.each([
    ["unite", 700],
    ["subtract", 300],
    ["intersect", 100],
    ["exclude", 600],
  ] as const)("%s gives the right area", (op, expected) => {
    two();
    engine.selectAll();
    engine.booleanOp(op);
    expect(engine.docItems().length).toBe(1);
    expect(engine.evenOddArea(engine.docItems()[0])).toBeCloseTo(expected, 2);
  });

  it("subtracting a hole circle leaves a compound path that exports two contours", () => {
    engine.loadDocument(doc([pathObj("plate", "cut", [rectNodes(0, 0, 50, 20)]), pathObj("hole", "cut", [circleNodes(25, 10, 5)])]));
    engine.selectAll();
    engine.booleanOp("subtract");
    const exported = engine.exportDocument().objects[0] as PathObject;
    expect(exported.contours.length).toBe(2);
    expect(engine.evenOddArea(engine.docItems()[0])).toBeCloseTo(1000 - Math.PI * 25, 0);
  });

  it("an empty intersection keeps the originals", () => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 10, 10)]), pathObj("b", "cut", [rectNodes(50, 50, 10, 10)])]));
    engine.selectAll();
    engine.booleanOp("intersect");
    expect(engine.docItems().length).toBe(2);
  });

  it("combine / break apart", () => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 30, 30)]), pathObj("b", "cut", [rectNodes(10, 10, 10, 10)])]));
    engine.selectAll();
    engine.combine();
    expect(engine.docItems().length).toBe(1);
    expect(engine.evenOddArea(engine.docItems()[0])).toBeCloseTo(800);
    engine.breakApart();
    expect(engine.docItems().length).toBe(2);
  });
});

describe("node editing", () => {
  beforeEach(() => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 20, 20)])]));
    engine.selectById(["a"]);
    engine.setTool("node");
  });
  const path = () => engine.itemById("a") as paper.Path;

  it("targets the selected path's nodes", () => {
    expect(engine.nodeTargets).toEqual([path()]);
  });

  it("deletes nodes but never below a valid shape", () => {
    engine.selectedSegments = [path().segments[0]];
    engine.deleteSelectedNodes();
    expect(path().segments.length).toBe(3);
    engine.selectedSegments = [path().segments[0]];
    engine.deleteSelectedNodes();
    expect(path().segments.length).toBe(3);
  });

  it("inserts a node between two adjacent selected nodes", () => {
    engine.selectedSegments = [path().segments[0], path().segments[1]];
    engine.insertNodes();
    expect(path().segments.length).toBe(5);
    expect(path().segments[1].point.x).toBeCloseTo(10);
  });

  it("converts nodes between corner and smooth", () => {
    engine.selectedSegments = [path().segments[1]];
    engine.setNodeType("smooth");
    expect(engine.isSmooth(path().segments[1])).toBe(true);
    engine.setNodeType("corner");
    expect(engine.isSmooth(path().segments[1])).toBe(false);
    expect(path().segments[1].handleIn.length).toBe(0);
  });

  it("moves a single node by coordinates", () => {
    engine.selectedSegments = [path().segments[2]];
    engine.setSingleNodePosition(30, 25);
    expect(path().segments[2].point.x).toBe(30);
    expect(engine.selectionInfo().singleNode).toMatchObject({ x: 30, y: 25 });
  });

  it("opens/closes, reverses and flattens", () => {
    engine.toggleClosed();
    expect(path().closed).toBe(false);
    engine.toggleClosed();
    expect(path().closed).toBe(true);
    const wasClockwise = path().clockwise;
    engine.reversePaths();
    expect(path().clockwise).toBe(!wasClockwise);
  });
});

describe("dimensions", () => {
  it("round-trips and follows the object when it is moved", () => {
    engine.loadDocument(doc([{ id: "d1", type: "dimension", layer: "dimensions", a: [0, 0], b: [50, 0], offset: 8, label: null }]));
    expect(engine.exportDocument().objects[0]).toMatchObject({ type: "dimension", a: [0, 0], b: [50, 0], offset: 8 });
    engine.selectById(["d1"]);
    expect(engine.selectionInfo().dimension?.length).toBeCloseTo(50);
    engine.setSelectionBounds({ x: 10, y: 20 });
    const moved = engine.exportDocument().objects[0];
    if (moved.type !== "dimension") throw new Error("expected a dimension");
    expect(moved.a[0]).toBeCloseTo(10);
    engine.setDimensionProps({ offset: -6, label: "Ø 10" });
    const edited = engine.exportDocument().objects[0];
    expect(edited).toMatchObject({ offset: -6, label: "Ø 10" });
  });
});

describe("layers", () => {
  it("adds, hides, locks and deletes layers with their objects", () => {
    engine.loadDocument(doc([pathObj("a", "holes", [rectNodes(0, 0, 5, 5)]), pathObj("b", "cut", [rectNodes(0, 0, 5, 5)])]));
    const added = engine.addLayer("Marquage", "engrave");
    expect(engine.activeLayerId).toBe(added.id);
    engine.updateLayer("holes", { visible: false });
    expect(engine.itemById("a")!.layer.visible).toBe(false);
    engine.updateLayer("holes", { role: "engrave" });
    expect(engine.exportDocument().layers.find((l) => l.id === "holes")!.role).toBe("engrave");
    expect(engine.removeLayer("holes")).toBe(true);
    expect(engine.itemById("a")).toBeUndefined();
    expect(engine.exportDocument().objects.map((o) => o.id)).toEqual(["b"]);
  });

  it("never deletes the last layer", () => {
    engine.loadDocument({ ...doc([]), layers: [LAYERS[0]] });
    expect(engine.removeLayer("cut")).toBe(false);
  });

  it("moves the selection to another layer", () => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 5, 5)])]));
    engine.selectById(["a"]);
    engine.moveSelectionToLayer("holes");
    expect((engine.exportDocument().objects[0] as PathObject).layer).toBe("holes");
  });
});

describe("tools (simulated pointer input)", () => {
  const P = (x: number, y: number) => new paper.Point(x, y);
  const mods = { shift: false, alt: false, ctrl: false };

  it("rectangle tool draws a snapped rectangle on the active layer", () => {
    engine.snapToNodes = false;
    engine.setTool("rect");
    const h = engine.activeHandler;
    h.down(P(10.2, 10.2), mods);
    h.drag(P(60.1, 40.4), mods);
    h.up(P(60.1, 40.4), mods);
    const obj = engine.exportDocument().objects[0] as PathObject;
    expect(obj.layer).toBe("cut");
    const b = engine.docItems()[0].bounds;
    expect([b.x, b.y, b.width, b.height]).toEqual([10, 10, 50, 30]);
  });

  it("ellipse + shift draws a circle", () => {
    engine.snapToNodes = false;
    engine.setTool("ellipse");
    const h = engine.activeHandler;
    h.down(P(0, 0), mods);
    h.drag(P(20, 8), { ...mods, shift: true });
    h.up(P(20, 8), { ...mods, shift: true });
    const b = engine.docItems()[0].bounds;
    expect(b.width).toBeCloseTo(20);
    expect(b.height).toBeCloseTo(20);
  });

  it("pen tool builds a closed Bézier shape when the first point is clicked again", () => {
    engine.snapToNodes = false;
    engine.setTool("pen");
    const h = engine.activeHandler;
    for (const [x, y] of [[0, 0], [40, 0], [40, 20]]) {
      h.down(P(x, y), mods);
      h.up(P(x, y), mods);
    }
    h.down(P(0, 20), mods);
    h.drag(P(0, 28), mods); // drag creates smooth handles
    h.up(P(0, 28), mods);
    h.down(P(0.5, 0.5), mods); // close on the first point
    const obj = engine.exportDocument().objects[0] as PathObject;
    expect(obj.closed).toBe(true);
    expect(obj.contours[0].length).toBe(4);
    expect(obj.contours[0][3].oy).toBeCloseTo(8);
    expect(obj.contours[0][3].iy).toBeCloseTo(-8);
  });

  it("pen tool refuses to draw on a locked layer", () => {
    engine.updateLayer("cut", { locked: true });
    engine.setTool("pen");
    engine.activeHandler.down(P(0, 0), mods);
    engine.activeHandler.up(P(0, 0), mods);
    engine.activeHandler.key("Enter");
    expect(engine.docItems().length).toBe(0);
  });

  it("select tool moves an object with grid snap and records one undo step", () => {
    engine.snapToNodes = false;
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 20, 20)])]));
    const h = engine.activeHandler;
    h.down(P(10, 10), mods);
    h.drag(P(34.4, 30.3), mods);
    h.up(P(34.4, 30.3), mods);
    const b = engine.itemById("a")!.bounds;
    expect([b.x, b.y]).toEqual([24, 20]);
    engine.undo();
    expect(engine.itemById("a")!.bounds.x).toBeCloseTo(0);
  });

  it("dimension tool places a dimension between two clicks", () => {
    engine.snapToNodes = false;
    engine.setTool("dimension");
    const h = engine.activeHandler;
    h.down(P(0, 0), mods);
    h.down(P(30, 0), mods);
    const dim = engine.exportDocument().objects[0];
    expect(dim).toMatchObject({ type: "dimension", layer: "dimensions", a: [0, 0], b: [30, 0] });
  });

  it("rubber-band selects only fully enclosed objects", () => {
    engine.loadDocument(doc([pathObj("a", "cut", [rectNodes(0, 0, 10, 10)]), pathObj("b", "cut", [rectNodes(40, 0, 10, 10)])]));
    const h = engine.activeHandler;
    h.down(P(-5, -5), mods);
    h.drag(P(20, 20), mods);
    h.up(P(20, 20), mods);
    expect(engine.selection.map((i) => i.data.id)).toEqual(["a"]);
  });
});

describe("svg import", () => {
  it("detects the unit scale", () => {
    expect(detectSvgScaleToMm('<svg width="100mm" height="50mm" viewBox="0 0 100 50">')).toBeCloseTo(1);
    expect(detectSvgScaleToMm('<svg width="4in" viewBox="0 0 400 200">')).toBeCloseTo(0.254);
    expect(detectSvgScaleToMm('<svg width="200" height="100">')).toBeCloseTo(25.4 / 96);
    expect(detectSvgScaleToMm("<svg>")).toBeCloseTo(25.4 / 96);
  });

  it("imports shapes in millimetres, baking nested transforms", () => {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">' +
      '<g transform="translate(10 5)"><rect x="0" y="0" width="30" height="20"/><circle cx="50" cy="10" r="5"/></g></svg>';
    expect(engine.importSvg(svg)).toBe(2);
    const sel = engine.selectionBounds()!;
    expect(sel.x).toBeCloseTo(0);
    expect(sel.width).toBeCloseTo(55, 1); // 0..30 and 45..55
    const rect = engine.docItems().find((i) => Math.abs(i.bounds.width - 30) < 0.01);
    expect(rect?.bounds.height).toBeCloseTo(20);
  });
});
