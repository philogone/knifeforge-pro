import paper from "paper";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { arcThrough, chamferCorner, circleNodes, circleThrough, dragCurvePoint, filletCorner, holeCentres, symmetricComplete, type Vec } from "../drafting";
import { EditorEngine } from "../engine";
import type { DesignDocument, DocNode, PathObject } from "../types";

// ---- independent checks --------------------------------------------------------------------
/** Points along the Bézier curves between consecutive nodes. */
function samples(nodes: DocNode[], perCurve = 40): Vec[] {
  const pts: Vec[] = [];
  for (let i = 0; i + 1 < nodes.length; i++) {
    const a = nodes[i];
    const b = nodes[i + 1];
    const p0: Vec = [a.x, a.y];
    const p1: Vec = [a.x + a.ox, a.y + a.oy];
    const p2: Vec = [b.x + b.ix, b.y + b.iy];
    const p3: Vec = [b.x, b.y];
    for (let k = 0; k <= perCurve; k++) {
      const t = k / perCurve;
      const u = 1 - t;
      pts.push([
        u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
      ]);
    }
  }
  return pts;
}
const dist = (a: Vec, b: Vec) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const maxRadialError = (nodes: DocNode[], c: Vec, r: number) => Math.max(...samples(nodes).map((p) => Math.abs(dist(p, c) - r)));
const shoelace = (pts: Vec[]) => Math.abs(pts.reduce((s, p, i) => s + p[0] * pts[(i + 1) % pts.length][1] - pts[(i + 1) % pts.length][0] * p[1], 0)) / 2;

describe("fillet", () => {
  it("rounds a right angle with an arc tangent to both edges, on its circle within 0.027 % of r", () => {
    const res = filletCorner([0, 10], [0, 0], [10, 0], 3);
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    const n = res.nodes;
    expect([n[0].x, n[0].y]).toEqual([0, 3]);
    expect([n[n.length - 1].x, n[n.length - 1].y]).toEqual([3, 0]);
    expect(maxRadialError(n, [3, 3], 3)).toBeLessThan(3 * 2.8e-4);
    // tangent to the edges: first handle along the vertical edge, last along the horizontal one
    expect(n[0].ox).toBeCloseTo(0, 9);
    expect(n[n.length - 1].iy).toBeCloseTo(0, 9);
  });

  it("handles acute and obtuse corners (sharp ones need two Bézier pieces)", () => {
    for (const deg of [30, 60, 120, 150]) {
      const t = (deg * Math.PI) / 180;
      const prev: Vec = [40, 0];
      const next: Vec = [40 * Math.cos(t), -40 * Math.sin(t)];
      const res = filletCorner(prev, [0, 0], next, 2);
      expect(res.ok, `${deg}°`).toBe(true);
      if (!res.ok) continue;
      // independent centre: on the bisector at r / sin(θ/2)
      const bis = [Math.cos(t / 2), -Math.sin(t / 2)];
      const c: Vec = [(bis[0] * 2) / Math.sin(t / 2), (bis[1] * 2) / Math.sin(t / 2)];
      expect(maxRadialError(res.nodes, c, 2), `${deg}°`).toBeLessThan(2 * 2.8e-4 + 1e-4);
      expect(res.setback).toBeCloseTo(2 / Math.tan(t / 2), 9);
      expect(res.nodes.length).toBe(deg < 90 ? 3 : 2); // sweep 180-θ: over 90° for θ < 90°
    }
  });

  it("refuses a radius that does not fit, a straight 'corner' and a non-positive radius", () => {
    expect(filletCorner([0, 2], [0, 0], [10, 0], 3)).toEqual({ ok: false, error: "tooLarge" });
    expect(filletCorner([0, 10], [0, 0], [10, 0], 3, 2.9)).toEqual({ ok: false, error: "tooLarge" });
    expect(filletCorner([-10, 0], [0, 0], [10, 0], 3)).toEqual({ ok: false, error: "notCorner" });
    expect(filletCorner([0, 10], [0, 0], [10, 0], 0)).toEqual({ ok: false, error: "invalid" });
  });
});

describe("chamfer", () => {
  it("cuts the corner at the same distance on both edges", () => {
    const res = chamferCorner([0, 10], [0, 0], [10, 0], 2);
    expect(res).toMatchObject({ ok: true, nodes: [{ x: 0, y: 2 }, { x: 2, y: 0 }] });
    expect(chamferCorner([0, 1], [0, 0], [10, 0], 2)).toEqual({ ok: false, error: "tooLarge" });
  });
});

describe("arc through three points", () => {
  it("passes through the middle point and stays on the circle", () => {
    const nodes = arcThrough([-10, 0], [0, -10], [10, 0]);
    expect(nodes.length).toBe(3); // 180° in two 90° pieces
    expect(maxRadialError(nodes, [0, 0], 10)).toBeLessThan(10 * 2.8e-4);
    expect(Math.min(...samples(nodes).map((p) => p[1]))).toBeCloseTo(-10, 3); // goes over the top, through (0, -10)
    // the same ends with the middle point below: the arc goes under
    expect(Math.max(...samples(arcThrough([-10, 0], [0, 10], [10, 0])).map((p) => p[1]))).toBeCloseTo(10, 3);
  });

  it("degrades to a straight segment for aligned points", () => {
    expect(arcThrough([0, 0], [5, 0], [10, 0]).length).toBe(2);
    expect(circleThrough([0, 0], [5, 0], [10, 0])).toBeNull();
  });
});

describe("symmetry", () => {
  it("closes a half outline drawn from the axis to the axis with its mirror image", () => {
    const half: DocNode[] = [
      { x: 0.3, y: 0, ix: 0, iy: 0, ox: 4, oy: 0 },
      { x: 15, y: 5, ix: 0, iy: -3, ox: 0, oy: 3 },
      { x: 12, y: 30, ix: 0, iy: 0, ox: 0, oy: 0 },
      { x: -0.2, y: 40, ix: 0, iy: 0, ox: 0, oy: 0 },
    ];
    const res = symmetricComplete(half, { axis: "x", pos: 0 }, 0.5);
    expect("closed" in res).toBe(true);
    if (!("closed" in res)) return;
    const c = res.closed;
    expect(c.map((n) => [n.x, n.y])).toEqual([[0, 0], [15, 5], [12, 30], [0, 40], [-12, 30], [-15, 5]]);
    // mirrored handles: the copy of (15, 5) walked backwards
    expect(c[5]).toMatchObject({ ix: 0, iy: 3, ox: 0, oy: -3 });
    // the joint on the axis keeps the drawn handle and gets its mirror on the other side
    expect(c[0]).toMatchObject({ ox: 4, oy: 0, ix: -4, iy: 0 });
    // the whole outline is symmetric: every node has its mirror
    for (const n of c) expect(c.some((m) => Math.abs(m.x + n.x) < 1e-9 && Math.abs(m.y - n.y) < 1e-9)).toBe(true);
  });

  it("mirrors apart when the ends are off the axis", () => {
    const res = symmetricComplete([{ x: 5, y: 0, ix: 0, iy: 0, ox: 0, oy: 0 }, { x: 8, y: 10, ix: 0, iy: 0, ox: 0, oy: 0 }], { axis: "y", pos: 20 }, 0.5);
    expect(res).toEqual({ mirror: [{ x: 5, y: 40, ix: 0, iy: 0, ox: 0, oy: 0 }, { x: 8, y: 30, ix: 0, iy: 0, ox: 0, oy: 0 }] });
  });
});

describe("hole patterns", () => {
  it("lays out a row of holes from the first centre, angle read y-up", () => {
    expect(holeCentres({ x: 10, y: 50, diameter: 4, count: 3, pitch: 12.5, angle: 0 })).toEqual([[10, 50], [22.5, 50], [35, 50]]);
    expect(holeCentres({ x: 0, y: 0, diameter: 4, count: 2, pitch: 10, angle: 90 })).toEqual([[0, 0], [0, -10]]);
  });

  it("draws circles of the exact diameter (4-node Bézier)", () => {
    const c = circleNodes(5, 5, 2.38);
    expect(maxRadialError([...c, c[0]], [5, 5], 2.38)).toBeLessThan(2.38 * 2.8e-4);
  });
});

// ---- through the engine ----------------------------------------------------------------------
const P = (x: number, y: number) => new paper.Point(x, y);
const mods = { shift: false, alt: false, ctrl: false };
const rectNodes = (w: number, h: number): DocNode[] =>
  [[0, 0], [w, 0], [w, h], [0, h]].map(([x, y]) => ({ x, y, ix: 0, iy: 0, ox: 0, oy: 0 }));
function doc(objects: PathObject[]): DesignDocument {
  return {
    version: 1,
    unit: "mm",
    layers: [
      { id: "cut", name: "Découpe", role: "cut", visible: true, locked: false },
      { id: "holes", name: "Perçages", role: "hole", visible: true, locked: false },
    ],
    objects,
  };
}

let engine: EditorEngine;
beforeEach(() => {
  const canvas = document.createElement("canvas");
  canvas.width = 800;
  canvas.height = 600;
  engine = new EditorEngine(canvas, { headless: true });
  engine.snapOptions = { nodes: false, intersections: false, midpoints: false, centers: false, path: false, guides: false, grid: false };
});
afterEach(() => engine.destroy());

describe("engine: corners", () => {
  const plate = () => engine.loadDocument(doc([{ id: "p", type: "path", layer: "cut", name: null, closed: true, contours: [rectNodes(60, 20)] }]));
  const selectAllNodes = () => {
    engine.selectById(["p"]);
    engine.setTool("node");
    engine.selectedSegments = [...engine.nodeTargets[0].segments];
  };

  it("fillets the four corners of a plate: area = w·h − (4 − π)·r²", () => {
    plate();
    selectAllNodes();
    expect(engine.roundCorners("fillet", 4)).toEqual({ done: 4, skipped: {} });
    expect(engine.evenOddArea(engine.itemById("p")!)).toBeCloseTo(60 * 20 - (4 - Math.PI) * 16, 1);
    engine.undo();
    expect(engine.evenOddArea(engine.itemById("p")!)).toBeCloseTo(1200, 6);
  });

  it("chamfers: area = w·h − 4 · d²/2", () => {
    plate();
    selectAllNodes();
    engine.roundCorners("chamfer", 3);
    expect(engine.evenOddArea(engine.itemById("p")!)).toBeCloseTo(1200 - 4 * 4.5, 6);
  });

  it("limits each corner to half an edge shared by two treated corners, and reports what it skipped", () => {
    plate();
    selectAllNodes();
    // r = 12 needs 12 mm on each side: fits the 60 mm edges but not half of the 20 mm ones
    expect(engine.roundCorners("fillet", 12)).toEqual({ done: 0, skipped: { tooLarge: 4 } });
    engine.loadDocument(doc([{ id: "c", type: "path", layer: "holes", name: null, closed: true, contours: [circleNodes(0, 0, 5)] }]));
    engine.selectById(["c"]);
    engine.setTool("node");
    engine.selectedSegments = [engine.nodeTargets[0].segments[0]];
    expect(engine.roundCorners("fillet", 1)).toEqual({ done: 0, skipped: { curvedEdge: 1 } });
  });
});

describe("engine: drawing aids", () => {
  it("node tool: dragging the middle of a straight edge bends it, in one undo step", () => {
    const tri = [[70, 50], [150, 40], [150, 60]].map(([x, y]) => ({ x, y, ix: 0, iy: 0, ox: 0, oy: 0 }));
    engine.loadDocument(doc([{ id: "t", type: "path", layer: "cut", name: null, closed: true, contours: [tri] }]));
    engine.setTool("node");
    const h = engine.activeHandler;
    // grab the bottom edge (150,60) → (70,50) at its middle and pull it 6 mm down
    h.down(P(110, 55), mods);
    h.drag(P(110, 58), mods);
    h.drag(P(110, 61), mods);
    h.up(P(110, 61), mods);
    const edge = (engine.docItems()[0] as paper.Path).curves[2];
    expect(edge.isStraight()).toBe(false);
    const mid = edge.getPointAtTime(0.5);
    expect(mid.x).toBeCloseTo(110, 6);
    expect(mid.y).toBeCloseTo(61, 6);
    expect([edge.point1.x, edge.point1.y, edge.point2.x, edge.point2.y]).toEqual([150, 60, 70, 50]);
    engine.undo();
    expect((engine.docItems()[0] as paper.Path).curves[2].isStraight()).toBe(true);
  });

  it("node tool: bending a segment never changes its neighbours, even through a smooth node", () => {
    // blade-like outline whose tip (first node) is smooth: the spine leaves it, the edge comes back
    const nodes = [
      { x: 70, y: 50, ix: 6, iy: 8, ox: -6, oy: -8 },
      { x: 150, y: 40, ix: -30, iy: 0, ox: 0, oy: 0 },
      { x: 150, y: 60, ix: 0, iy: 0, ox: 0, oy: 0 },
    ];
    engine.loadDocument(doc([{ id: "b", type: "path", layer: "cut", name: null, closed: true, contours: [nodes] }]));
    engine.setTool("node");
    const path = () => engine.docItems()[0] as paper.Path;
    const spine = () => path().curves[0].points.map((q) => [q.x, q.y]);
    const before = spine();
    expect(engine.isSmooth(path().segments[0])).toBe(true);
    const h = engine.activeHandler;
    const grab = path().curves[2].getPointAtTime(0.5);
    h.down(grab, mods);
    h.drag(grab.add([0, 5]), mods);
    h.up(grab.add([0, 5]), mods);
    expect(spine()).toEqual(before);
    expect(path().curves[1].isStraight()).toBe(true);
  });

  it("the pen takes typed lengths and angles", () => {
    engine.setTool("pen");
    const h = engine.activeHandler;
    h.down(P(0, 0), mods);
    h.up(P(0, 0), mods);
    expect(engine.toolNumeric(50, 0)).toBe(true);
    expect(engine.toolNumeric(20, 90)).toBe(true); // straight up on screen
    expect(engine.toolNumeric(10, 210)).toBe(true);
    h.key("Enter");
    const obj = engine.exportDocument().objects[0] as PathObject;
    const pts = obj.contours[0].map((n) => [n.x, n.y]);
    expect(pts.slice(0, 3)).toEqual([[0, 0], [50, 0], [50, -20]]);
    expect(pts[3][0]).toBeCloseTo(50 - 10 * Math.cos(Math.PI / 6), 4);
    expect(pts[3][1]).toBeCloseTo(-20 + 5, 4);
    expect(engine.toolNumeric(5, 0)).toBe(false); // no path in progress
  });

  it("symmetry: a half outline drawn with the pen becomes one closed symmetric shape", () => {
    engine.symmetry = { axis: "x", pos: 0 };
    engine.setTool("pen");
    const h = engine.activeHandler;
    for (const [x, y] of [[0, 0], [15, 5], [12, 30], [0.4, 40]]) {
      h.down(P(x, y), mods);
      h.up(P(x, y), mods);
    }
    h.key("Enter");
    const objs = engine.exportDocument().objects as PathObject[];
    expect(objs.length).toBe(1);
    expect(objs[0].closed).toBe(true);
    const pts = objs[0].contours[0].map((n) => [n.x, n.y] as Vec);
    expect(pts).toEqual([[0, 0], [15, 5], [12, 30], [0, 40], [-12, 30], [-15, 5]]);
    expect(engine.evenOddArea(engine.docItems()[0])).toBeCloseTo(shoelace(pts), 6);
  });

  it("arc tool: start, end, then a point on the arc", () => {
    engine.setTool("arc");
    const h = engine.activeHandler;
    h.down(P(-10, 0), mods);
    h.down(P(10, 0), mods);
    h.down(P(0, -10), mods);
    const b = engine.docItems()[0].bounds;
    expect(b.width).toBeCloseTo(20, 6);
    expect(b.height).toBeCloseTo(10, 3);
    expect((engine.exportDocument().objects[0] as PathObject).closed).toBe(false);
  });

  it("open paths are drawn as lines, not filled shapes", () => {
    engine.setTool("arc");
    const h = engine.activeHandler;
    h.down(P(-10, 0), mods);
    h.down(P(10, 0), mods);
    h.down(P(0, -10), mods);
    const arc = engine.docItems()[0] as paper.Path;
    expect(arc.fillColor).toBeNull();
    engine.setTool("node");
    engine.toggleClosed();
    expect((engine.docItems()[0] as paper.Path).fillColor).not.toBeNull();
  });

  it("adds a row of holes on the hole layer, exact diameter, one undo step", () => {
    engine.loadDocument(doc([]));
    expect(engine.addHoles({ x: 10, y: 10, diameter: 4.76, count: 3, pitch: 15, angle: 0 })).toBe(3);
    const objs = engine.exportDocument().objects;
    expect(objs.map((o) => o.layer)).toEqual(["holes", "holes", "holes"]);
    const b = engine.docItems()[2].bounds;
    expect(b.width).toBeCloseTo(4.76, 9);
    expect(b.center.x).toBeCloseTo(40, 9);
    engine.undo();
    expect(engine.exportDocument().objects.length).toBe(0);
  });
});

describe("bending a segment by dragging it", () => {
  const at = (p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: number): Vec => {
    const u = 1 - t;
    return [0, 1].map((k) => u * u * u * p0[k] + 3 * u * u * t * p1[k] + 3 * u * t * t * p2[k] + t * t * t * p3[k]) as Vec;
  };

  it("moves the grabbed point by exactly the drag, ends fixed, wherever it is grabbed", () => {
    const p0: Vec = [70, 50];
    const p3: Vec = [150, 60];
    for (const t of [0.1, 0.25, 0.5, 0.7, 0.9]) {
      const before = at(p0, p0, p3, p3, t); // a straight line: handles on the ends
      const [c1, c2] = dragCurvePoint(p0, p0, p3, p3, t, [3, 8]);
      const after = at(p0, c1, c2, p3, t);
      expect(after[0] - before[0]).toBeCloseTo(3, 9);
      expect(after[1] - before[1]).toBeCloseTo(8, 9);
    }
  });

  it("is symmetric when grabbed in the middle, and leans on the near handle otherwise", () => {
    const [a, b] = dragCurvePoint([0, 0], [0, 0], [100, 0], [100, 0], 0.5, [0, 10]);
    expect(a[1]).toBeCloseTo(b[1], 9);
    expect(a[1]).toBeCloseTo(40 / 3, 9); // 3·¼·½·(d1 + d2) = 10
    const [c, d] = dragCurvePoint([0, 0], [0, 0], [100, 0], [100, 0], 0.15, [0, 10]);
    expect(d[1]).toBe(0); // grabbed near the start: only the start handle moves
    expect(c[1]).toBeGreaterThan(10);
  });

  it("keeps the handles bounded right next to a node", () => {
    const [a] = dragCurvePoint([0, 0], [0, 0], [100, 0], [100, 0], 0.0001, [0, 1]);
    expect(Math.abs(a[1])).toBeLessThan(10);
  });
});
