<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";

import EditorIcon, { type EditorIconName } from "@/components/EditorIcon.vue";
import { saveBlob } from "@/composables/useApi";
import { useSnapshotDirty } from "@/composables/useSnapshotDirty";
import { initialPlacement, loadImageFile, mmPerPixel, type BackgroundState, type Straighten } from "@/editor/background";
import { ROLE_STYLE } from "@/editor/constants";
import { STANDARD_HOLES_MM, type Axis } from "@/editor/drafting";
import { SHAPES, documentParts, normalizeParams, partsBounds, placeParts, type ShapePart } from "@/editor/shapes";
import { documentToSvg } from "@/editor/svgPreview";
import { BUNDLED_FONTS, loadFont, missingGlyphs, textContours } from "@/editor/text";
import { EditorEngine, formatMm } from "@/editor/engine";
import type { AlignKind, BooleanOp, CornerReport, Measurement, SnapKind, SnapOptions } from "@/editor/engine";
import type { DocLayer, Guide, LayerRole, SelectionInfo, ToolName } from "@/editor/types";
import { RULER_SIZE, drawGrid, drawRulers, screenToWorld } from "@/editor/view";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useTheme } from "@/composables/useTheme";
import { screenPxPerMm } from "@/editor/screenScale";
import { useAppStore } from "@/stores/app.store";
import type { Design, DesignKind, DesignSummary } from "@/types";

const { t, num } = useI18n();
const store = useAppStore();
const route = useRoute();

const kinds: DesignKind[] = ["blade", "handle_scale", "guard", "bolster", "sheath", "template", "other"];
const roles: LayerRole[] = ["cut", "hole", "engrave", "grind", "construction", "dimension"];
const tools: (ToolName & EditorIconName)[] = ["select", "node", "pen", "rect", "ellipse", "line", "polygon", "arc", "dimension", "measure", "pan"];
const transforms: { key: string; icon: EditorIconName; label: string; run: () => void }[] = [
  { key: "fh", icon: "flip-h", label: "editor.flipH", run: () => engine.value?.flipSelection("h") },
  { key: "fv", icon: "flip-v", label: "editor.flipV", run: () => engine.value?.flipSelection("v") },
  { key: "mh", icon: "mirror-h", label: "editor.mirrorH", run: () => engine.value?.mirrorCopy("h") },
  { key: "mv", icon: "mirror-v", label: "editor.mirrorV", run: () => engine.value?.mirrorCopy("v") },
  { key: "r90", icon: "rotate", label: "editor.rotate90", run: () => engine.value?.rotateSelection(90) },
  { key: "dup", icon: "duplicate", label: "editor.duplicate", run: () => engine.value?.duplicateSelection() },
];
const alignKinds: AlignKind[] = ["left", "centerH", "right", "top", "middleV", "bottom"];
const booleanOps: BooleanOp[] = ["unite", "subtract", "intersect", "exclude"];

const designId = computed(() => Number(route.params.id));
const design = ref<Design | null>(null);
const loadError = ref("");
const meta = reactive({ name: "", kind: "other" as DesignKind, notes: "", knife_model_id: 0, material_id: 0 });
const { dirty: metaDirty, markClean: markMetaClean } = useSnapshotDirty(() => ({ ...meta }));

const stage = ref<HTMLDivElement | null>(null);
const gridCanvas = ref<HTMLCanvasElement | null>(null);
const paperCanvas = ref<HTMLCanvasElement | null>(null);
const rulerCanvas = ref<HTMLCanvasElement | null>(null);
const engine = shallowRef<EditorEngine | null>(null);

const emptySel = (): SelectionInfo => ({
  count: 0, ids: [], bounds: null, name: null, layerId: null, mixedLayers: false,
  path: null, dimension: null, selectedNodes: 0, singleNode: null,
});
const sel = ref<SelectionInfo>(emptySel());
const tool = ref<ToolName>("select");
const layers = ref<DocLayer[]>([]);
const activeLayerId = ref("");
const zoomPct = ref(100);
const cursor = ref<[number, number]>([0, 0]);
const hintText = ref("");
const valueHint = ref("");
const dirty = ref(false);
const canUndo = ref(false);
const canRedo = ref(false);
const tab = ref<"object" | "layers" | "background" | "document">("object");
const saving = ref(false);
const status = ref("");
const statusIsError = ref(false);

const opts = reactive({ gridSize: 1, showGrid: true, cornerRadius: 0, polygonSides: 6, snapRadius: 10 });
const snapOpts = reactive<SnapOptions>({ nodes: true, intersections: true, midpoints: true, centers: true, path: false, guides: true, grid: true });
const snapKinds = Object.keys(snapOpts) as (keyof SnapOptions)[];
const guides = ref<Guide[]>([]);
const guideForm = reactive({ x: 0, y: 0 });
const measurement = ref<Measurement | null>(null);

// Reference image. Its own "unsaved" tracking: it is saved with the design but is not part of the
// document, so the engine's dirty flag (document only) does not see it. The data URL is keyed by
// length + tail so a multi-MB string is never re-serialised on every change.
const bg = ref<BackgroundState | null>(null);
const { dirty: bgDirty, markClean: markBgClean } = useSnapshotDirty(() => {
  const b = bg.value;
  if (!b) return null;
  return { ...b, image: `${b.image.length}:${b.image.slice(-48)}`, pixelWidth: undefined, pixelHeight: undefined };
});
const bgResolution = computed(() => (bg.value?.pixelWidth ? mmPerPixel(bg.value, bg.value.pixelWidth) : null));
// ---- lot 2: drawing aids
const drawing = ref(false);
const numeric = reactive({ length: "" as number | "", angle: 0 as number | "" });
const lengthInput = ref<HTMLInputElement | null>(null);
const symmetry = reactive({ axis: "" as "" | Axis["axis"], pos: 0 });
const cornerSize = ref(3);
const holes = reactive({ open: false, diameter: 4.76, x: 0, y: 0, count: 2, pitch: 20, angle: 0 });
const textForm = reactive({ open: false, busy: false, text: "", capHeight: 5, letterSpacing: 0, x: 0, y: 0, weight: "regular" as "regular" | "bold" | "custom", customName: "", error: "" });
let customFont: ArrayBuffer | null = null;
const calib = reactive({ open: false, a: [0, 0] as [number, number], b: [0, 0] as [number, number], real: "" as number | "", straighten: "horizontal" as Straighten, origin: false });
// ---- lot 3: perspective correction
const PERSPECTIVE_PRESETS: { key: string; w: number; h: number }[] = [
  { key: "a4", w: 297, h: 210 },
  { key: "a3", w: 420, h: 297 },
  { key: "letter", w: 279.4, h: 215.9 },
  { key: "card", w: 85.6, h: 53.98 },
];
const persp = reactive({ open: false, busy: false, corners: [] as [number, number][], preset: "", width: "" as number | "", height: "" as number | "", origin: false, error: "" });
/** the photo as it was before the last perspective correction, to undo it (not saved) */
const bgBeforeRectify = shallowRef<BackgroundState | null>(null);
// ---- lot 3: shape library
const library = reactive({
  open: false,
  source: "shapes" as "shapes" | "designs",
  shape: SHAPES[0].key,
  params: {} as Record<string, Record<string, number | "">>,
  designId: 0,
  designs: [] as DesignSummary[],
  loading: false,
  x: 0 as number | "",
  y: 0 as number | "",
});
const designParts = shallowRef<Map<number, ShapePart[]>>(new Map());
const lockRatio = ref(true);
const rotateBy = ref(0);
const offsetForm = reactive({ distance: 1, join: "round" as "round" | "mitre" | "bevel", keep: false });
const nodeXY = reactive({ x: 0, y: 0 });
const bounds = reactive({ x: 0, y: 0, w: 0, h: 0 });
const dimForm = reactive({ offset: 8, label: "" });

const unsaved = computed(() => dirty.value || metaDirty.value || bgDirty.value);

function setStatus(msg: string, error = false) {
  status.value = msg;
  statusIsError.value = error;
}

// ------------------------------------------------------------------ drawing
let resizeObserver: ResizeObserver | null = null;
let offs: (() => void)[] = [];

function paintBackground() {
  const e = engine.value;
  const c = gridCanvas.value;
  if (!e || !c) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  drawGrid(ctx, e.viewTransform, { step: e.gridSize, show: opts.showGrid });
}
function paintRulers() {
  const e = engine.value;
  const c = rulerCanvas.value;
  if (!e || !c) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  drawRulers(ctx, e.viewTransform, e.cursor, e.guides, e.previewGuide, tool.value === "pen" ? e.symmetry : null);
}

function sizeCanvases() {
  const e = engine.value;
  const host = stage.value;
  if (!e || !host) return;
  const w = Math.floor(host.clientWidth);
  const h = Math.floor(host.clientHeight);
  if (w < 10 || h < 10) return;
  const dpr = window.devicePixelRatio || 1;
  for (const c of [gridCanvas.value, rulerCanvas.value]) {
    if (!c) continue;
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
    c.style.width = `${w}px`;
    c.style.height = `${h}px`;
  }
  e.resize(w, h);
  paintBackground();
  paintRulers();
}

function refreshState() {
  const e = engine.value;
  if (!e) return;
  dirty.value = e.dirty;
  canUndo.value = e.canUndo;
  canRedo.value = e.canRedo;
  layers.value = e.layers.map((l) => ({ ...l }));
  activeLayerId.value = e.activeLayerId;
}

function syncSelectionForms(s: SelectionInfo) {
  if (s.bounds) {
    bounds.x = round(s.bounds.x);
    bounds.y = round(s.bounds.y);
    bounds.w = round(s.bounds.w);
    bounds.h = round(s.bounds.h);
  }
  if (s.singleNode) {
    nodeXY.x = s.singleNode.x;
    nodeXY.y = s.singleNode.y;
  }
  if (s.dimension) {
    dimForm.offset = s.dimension.offset;
    dimForm.label = s.dimension.label ?? "";
  }
}
const round = (n: number) => Math.round(n * 1000) / 1000;

function attachEngine(doc: Design) {
  const canvas = paperCanvas.value!;
  const e = new EditorEngine(canvas);
  engine.value = e;
  e.snapLabels = Object.fromEntries(
    (["node", "intersection", "midpoint", "center", "path", "guide"] as SnapKind[]).map((k) => [k, t(`snap.${k}`)]),
  );
  e.loadDocument(doc.document, { resetHistory: true, fit: false });
  e.gridSize = opts.gridSize;
  e.snapOptions = { ...snapOpts };
  guides.value = e.guides.map((g) => ({ ...g }));
  offs = [
    e.on("change", refreshState),
    e.on("selection", (s) => {
      sel.value = s;
      syncSelectionForms(s);
    }),
    e.on("view", () => {
      zoomPct.value = Math.round((e.zoom / screenPxPerMm()) * 100);
      paintBackground();
      paintRulers();
    }),
    e.on("cursor", (x, y) => {
      cursor.value = [x, y];
      paintRulers();
    }),
    e.on("tool", (name) => {
      tool.value = name;
      if (name !== "measure") measurement.value = null;
    }),
    e.on("guides", () => {
      guides.value = e.guides.map((g) => ({ ...g }));
      paintRulers();
    }),
    e.on("measure", (m) => (measurement.value = m)),
    e.on("drawing", (on) => {
      drawing.value = on;
      if (!on) numeric.length = "";
    }),
    e.on("background", () => (bg.value = e.background)),
    e.on("calibrate", (a, b) => {
      calib.a = a;
      calib.b = b;
      // left empty on purpose: pre-filling the measured value would let "Apply" mark an
      // uncalibrated image as calibrated
      calib.real = "";
      calib.open = true;
    }),
    e.on("perspective", (corners) => {
      persp.corners = corners;
      persp.error = "";
      if (persp.preset) setPerspectivePreset(persp.preset); // the sides may have been clicked the other way round
      persp.open = true;
    }),
    e.on("layers", refreshState),
    e.on("hint", (key) => {
      const text = t(key);
      hintText.value = text;
    }),
    e.on("value", (txt) => (valueHint.value = txt)),
  ];
  sizeCanvases();
  e.zoomToFit();
  refreshState();
  e.setTool("select");
  hintText.value = t(e.activeHandler.hint);
}

async function load() {
  try {
    const d = await store.fetchDesign(designId.value);
    design.value = d;
    meta.name = d.name;
    meta.kind = d.kind;
    meta.notes = d.notes ?? "";
    meta.knife_model_id = d.knife_model_id ?? 0;
    meta.material_id = d.material_id ?? 0;
    markMetaClean();
    await nextTick();
    attachEngine(d);
    engine.value?.setBackground(d.background ? { ...d.background } : null);
    markBgClean();
  } catch (err) {
    loadError.value = errorMessage(err, t, "common.error");
  }
}

onMounted(async () => {
  store.fetchKnifeModels().catch(() => undefined);
  store.fetchMaterials().catch(() => undefined);
  await load();
  if (stage.value) {
    resizeObserver = new ResizeObserver(() => sizeCanvases());
    resizeObserver.observe(stage.value);
  }
  offs.push(
    useTheme().onChange(() => {
      paintBackground();
      paintRulers();
    }) as () => void,
  );
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("beforeunload", onBeforeUnload);
  // arriving from a model or an order to print its plan
  if (route.query.plan === "1" && design.value) void openPlan();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeyDown);
  window.removeEventListener("keyup", onKeyUp);
  window.removeEventListener("beforeunload", onBeforeUnload);
  resizeObserver?.disconnect();
  offs.forEach((off) => off());
  engine.value?.destroy();
  engine.value = null;
  if (planUrl.value) URL.revokeObjectURL(planUrl.value);
});

function onBeforeUnload(ev: BeforeUnloadEvent) {
  if (unsaved.value) {
    ev.preventDefault();
    ev.returnValue = "";
  }
}

onBeforeRouteLeave(() => {
  if (unsaved.value && !window.confirm(t("editor.leaveConfirm"))) return false;
  return true;
});

watch(
  () => [opts.gridSize, opts.showGrid, opts.cornerRadius, opts.polygonSides, opts.snapRadius, { ...snapOpts }],
  () => {
    const e = engine.value;
    if (!e) return;
    e.setGridSize(Number(opts.gridSize));
    e.snapOptions = { ...snapOpts };
    e.snapRadiusPx = Math.min(40, Math.max(2, Number(opts.snapRadius) || 10));
    e.cornerRadius = Math.max(0, Number(opts.cornerRadius) || 0);
    e.polygonSides = Math.min(64, Math.max(3, Math.round(Number(opts.polygonSides) || 6)));
    paintBackground();
  },
  { deep: true },
);

// --------------------------------------------------------------------- save
async function save(): Promise<boolean> {
  const e = engine.value;
  if (!e || !design.value || saving.value) return false;
  saving.value = true;
  try {
    const updated = await store.updateDesign(design.value.id, {
      name: meta.name.trim() || design.value.name,
      kind: meta.kind,
      notes: meta.notes || null,
      knife_model_id: meta.knife_model_id || null,
      material_id: meta.material_id || null,
      document: e.exportDocument(),
      // the image is sent only when it changed: it can weigh several MB
      ...(bgDirty.value ? { background: bg.value ? backgroundPayload(bg.value) : null } : {}),
    });
    design.value = { ...design.value, ...updated };
    e.markSaved();
    markMetaClean();
    markBgClean();
    refreshState();
    setStatus(t("editor.saved"));
    return true;
  } catch (err) {
    setStatus(t("editor.saveFailed", { error: errorMessage(err, t) }), true);
    return false;
  } finally {
    saving.value = false;
  }
}

// export options, remembered between sessions
function storedNumber(key: string, fallback: number): number {
  try {
    const v = Number(localStorage.getItem(key));
    return Number.isFinite(v) && localStorage.getItem(key) !== null ? v : fallback;
  } catch {
    return fallback;
  }
}
const exportOpts = reactive({ kerf: storedNumber("knifeforge_export_kerf", 0), arcs: storedNumber("knifeforge_export_arcs", 0) === 1 });
watch(
  () => ({ ...exportOpts }),
  (o) => {
    try {
      localStorage.setItem("knifeforge_export_kerf", String(o.kerf || 0));
      localStorage.setItem("knifeforge_export_arcs", o.arcs ? "1" : "0");
    } catch {
      // not persisted
    }
  },
);

async function exportFile(kind: "export.svg" | "export.dxf") {
  if (unsaved.value && !(await save())) return;
  try {
    const kerf = Math.max(0, Math.min(3, Number(exportOpts.kerf) || 0));
    const blob = await store.downloadDesignFile(designId.value, kind, { curves: exportOpts.arcs ? "arcs" : "polylines", kerf });
    const suffix = kerf ? `_kerf${String(kerf).replace(".", ",")}` : "";
    saveBlob(blob, `${meta.name.replace(/[^\w.-]+/g, "_")}${suffix}.${kind.split(".")[1]}`);
  } catch (err) {
    setStatus(t("designs.exportFailed", { error: errorMessage(err, t) }), true);
  }
}

// ------------------------------------------------------------------ import
const fileInput = ref<HTMLInputElement | null>(null);
const exportMenu = ref<HTMLDetailsElement | null>(null);

function importFrom() {
  if (exportMenu.value) exportMenu.value.open = false;
  fileInput.value?.click();
}

function exportFrom(kind: "export.svg" | "export.dxf") {
  if (exportMenu.value) exportMenu.value.open = false;
  void exportFile(kind);
}
async function onImport(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !engine.value) return;
  const n = engine.value.importSvg(await file.text());
  setStatus(n ? t("editor.importDone", { n }) : t("editor.importNone"), !n);
}

// --------------------------------------------------------- background image
const bgInput = ref<HTMLInputElement | null>(null);

function backgroundPayload(b: BackgroundState) {
  const { image, cx, cy, width_mm, height_mm, rotation_deg, opacity, visible, locked, calibrated } = b;
  return { image, cx, cy, width_mm, height_mm, rotation_deg, opacity, visible, locked, calibrated };
}

function pickBackground() {
  if (bg.value && !window.confirm(t("bg.replaceConfirm"))) return;
  bgInput.value?.click();
}

async function onBackgroundFile(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  const e = engine.value;
  if (!file || !e) return;
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
    setStatus(t("bg.unsupported"), true);
    return;
  }
  try {
    const img = await loadImageFile(file);
    const v = e.viewTransform;
    // a first guess: 60 % of the visible width, centred in the view; calibration fixes the scale
    const placement = initialPlacement(img.width, img.height, [v.centerX, v.centerY], (v.width / v.zoom) * 0.6);
    e.setBackground({ image: img.dataUrl, ...placement, opacity: 0.5, visible: true, locked: true, calibrated: false });
    bgBeforeRectify.value = null;
    tab.value = "background";
    e.setTool("calibrate");
    setStatus(t("bg.imported"));
  } catch {
    setStatus(t("bg.loadFailed"), true);
  }
}

function removeBackground() {
  if (!window.confirm(t("bg.removeConfirm"))) return;
  engine.value?.setBackground(null);
  bgBeforeRectify.value = null;
  if (tool.value === "calibrate" || tool.value === "perspective") engine.value?.setTool("select");
}

function setBgField(field: "cx" | "cy" | "width_mm" | "height_mm" | "rotation_deg", ev: Event) {
  const e = engine.value;
  const b = bg.value;
  const value = Number((ev.target as HTMLInputElement).value);
  if (!e || !b || !Number.isFinite(value)) return;
  if (field === "width_mm" || field === "height_mm") {
    if (value <= 0) return;
    // the image keeps its aspect ratio
    const ratio = b.height_mm / b.width_mm;
    e.updateBackground(field === "width_mm" ? { width_mm: value, height_mm: value * ratio } : { height_mm: value, width_mm: value / ratio });
  } else {
    e.updateBackground({ [field]: value });
  }
}

function applyCalibration() {
  const e = engine.value;
  const real = Number(calib.real);
  if (!e || !(real > 0)) return;
  e.calibrateBackground(calib.a, calib.b, real, calib.straighten, calib.origin);
  calib.open = false;
  e.clearUi("calib");
  e.setTool("select");
  if (calib.origin) e.zoomToFit();
  const res = bgResolution.value;
  setStatus(res ? t("calib.done", { mm: formatMm(res) }) : t("bg.calibrated"));
}

function cancelCalibration() {
  calib.open = false;
  engine.value?.clearUi("calib");
}

function setPerspectivePreset(key: string) {
  const preset = PERSPECTIVE_PRESETS.find((p) => p.key === key);
  if (!preset) return;
  // the longer side along the longer clicked side 1→2 / 2→3
  const [a, b, c] = persp.corners;
  const first = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const second = Math.hypot(c[0] - b[0], c[1] - b[1]);
  [persp.width, persp.height] = first >= second ? [preset.w, preset.h] : [preset.h, preset.w];
}

async function applyPerspective() {
  const e = engine.value;
  const w = Number(persp.width);
  const h = Number(persp.height);
  const before = e?.background;
  if (!e || !before || !(w > 0) || !(h > 0) || persp.busy) return;
  persp.busy = true;
  persp.error = "";
  try {
    const plan = await e.rectifyBackground(persp.corners, w, h, persp.origin);
    if (!plan) {
      persp.error = t("persp.invalid");
      return;
    }
    bgBeforeRectify.value = before;
    persp.open = false;
    e.clearUi("persp");
    e.setTool("select");
    e.zoomToFit();
    setStatus(t("persp.done", { w: formatMm(w), h: formatMm(h), mm: formatMm(plan.sourceMmPerPx) }));
  } catch (err) {
    persp.error = t(err instanceof Error && err.message === "tooLarge" ? "persp.tooLarge" : "bg.loadFailed");
  } finally {
    persp.busy = false;
  }
}

function cancelPerspective() {
  persp.open = false;
  engine.value?.clearUi("persp");
}

function undoPerspective() {
  const e = engine.value;
  if (!e || !bgBeforeRectify.value) return;
  e.setBackground(bgBeforeRectify.value);
  bgBeforeRectify.value = null;
}

// ------------------------------------------------------------ drawing aids
watch([() => symmetry.axis, () => symmetry.pos, tool], () => {
  const e = engine.value;
  if (!e) return;
  const pos = Number(symmetry.pos);
  e.symmetry = symmetry.axis && Number.isFinite(pos) ? { axis: symmetry.axis, pos } : null;
  paintRulers();
});

/** Enter in the length field: place the typed node, or finish the path when the field is empty. */
function applyNumeric() {
  const e = engine.value;
  if (!e) return;
  if (numeric.length === "") {
    e.toolKey("Enter");
    (document.activeElement as HTMLElement | null)?.blur();
    return;
  }
  const length = Number(numeric.length);
  if (length > 0 && e.toolNumeric(length, Number(numeric.angle) || 0)) numeric.length = "";
}

function cancelNumeric() {
  engine.value?.toolKey("Escape");
  (document.activeElement as HTMLElement | null)?.blur();
}

function cornerMessage(r: CornerReport): string {
  const parts: string[] = [];
  if (r.done) parts.push(t("corner.done", { n: r.done }));
  for (const [why, n] of Object.entries(r.skipped)) parts.push(t(`corner.skip.${why}`, { n: n ?? 0 }));
  return parts.join(" · ") || t("corner.none");
}

function roundCorners(kind: "fillet" | "chamfer") {
  const e = engine.value;
  if (!e) return;
  if (!e.selectedSegments.length) return setStatus(t("corner.none"), true);
  const report = e.roundCorners(kind, Number(cornerSize.value));
  setStatus(cornerMessage(report), !report.done);
}

/** Dialogs open at a sensible spot: the selection's centre, else the middle of the view. */
function defaultPoint(): [number, number] {
  const e = engine.value;
  if (!e) return [0, 0];
  const b = sel.value.bounds;
  if (b) return [Math.round((b.x + b.w / 2) * 100) / 100, Math.round((b.y + b.h / 2) * 100) / 100];
  const v = e.viewTransform;
  return [Math.round(v.centerX), Math.round(v.centerY)];
}

function openHoles() {
  [holes.x, holes.y] = defaultPoint();
  holes.open = true;
}

function addHoles() {
  const e = engine.value;
  if (!e) return;
  const n = e.addHoles({ x: Number(holes.x), y: Number(holes.y), diameter: Number(holes.diameter), count: Number(holes.count), pitch: Number(holes.pitch), angle: Number(holes.angle) || 0 });
  if (n) {
    holes.open = false;
    setStatus(t("holes.done", { n }));
  }
}

// ------------------------------------------------------------ shape library
const currentShape = computed(() => SHAPES.find((d) => d.key === library.shape) ?? SHAPES[0]);

function shapeValues(key: string) {
  const def = SHAPES.find((d) => d.key === key)!;
  if (!library.params[key]) library.params[key] = Object.fromEntries(def.params.map((p) => [p.key, p.value]));
  return library.params[key];
}

/** Parts of the current choice, drawn from (0, 0); empty while a design is loading. */
const libraryParts = computed<ShapePart[]>(() => {
  if (library.source === "shapes") return currentShape.value.build(normalizeParams(currentShape.value, shapeValues(library.shape)));
  return designParts.value.get(library.designId) ?? [];
});

const librarySize = computed(() => {
  const b = partsBounds(libraryParts.value);
  return b ? { w: b.maxX - b.minX, h: b.maxY - b.minY } : null;
});

const libraryPreview = computed(() => {
  const roles: LayerRole[] = ["cut", "hole", "engrave", "grind"];
  const doc = {
    version: 1 as const,
    unit: "mm" as const,
    layers: roles.map((role) => ({ id: role, name: role, role, visible: true, locked: false })),
    objects: libraryParts.value.map((part, i) => ({ id: `p${i}`, type: "path" as const, layer: part.role, name: part.name, closed: part.closed, contours: part.contours })),
  };
  return documentToSvg(doc, 240);
});

/** Put the part's centre at the centre of the view (or of the selection); the fields show its top-left corner. */
function centreLibraryPlacement() {
  const size = librarySize.value;
  const [cx, cy] = defaultPoint();
  if (size) [library.x, library.y] = [Math.round((cx - size.w / 2) * 100) / 100, Math.round((cy - size.h / 2) * 100) / 100];
}

async function openLibrary() {
  library.open = true;
  centreLibraryPlacement();
  if (!library.designs.length) {
    try {
      library.designs = (await store.fetchDesigns()).filter((d) => d.id !== designId.value);
    } catch {
      library.designs = [];
    }
  }
}

async function pickLibraryDesign(id: number) {
  library.designId = id;
  if (designParts.value.has(id)) return centreLibraryPlacement();
  library.loading = true;
  try {
    const d = await store.fetchDesign(id);
    designParts.value = new Map(designParts.value).set(id, documentParts(d.document));
    centreLibraryPlacement();
  } catch (err) {
    setStatus(errorMessage(err, t), true);
  } finally {
    library.loading = false;
  }
}

function insertLibrary() {
  const e = engine.value;
  if (!e || !libraryParts.value.length) return;
  const n = e.insertParts(placeParts(libraryParts.value, Number(library.x) || 0, Number(library.y) || 0));
  if (n) {
    library.open = false;
    setStatus(t("library.done", { n }));
  }
}

function openText() {
  [textForm.x, textForm.y] = defaultPoint();
  textForm.error = "";
  textForm.open = true;
}

async function onFontFile(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  if (/\.woff2$/i.test(file.name)) {
    textForm.error = t("text.woff2");
    return;
  }
  customFont = await file.arrayBuffer();
  textForm.customName = file.name;
  textForm.weight = "custom";
}

async function addText() {
  const e = engine.value;
  const text = textForm.text.trim();
  if (!e || !text || !(Number(textForm.capHeight) > 0)) return;
  textForm.busy = true;
  textForm.error = "";
  try {
    const font = await loadFont(textForm.weight === "custom" && customFont ? customFont : await BUNDLED_FONTS[textForm.weight === "bold" ? "bold" : "regular"]());
    const missing = missingGlyphs(font, text);
    if (missing.length) {
      textForm.error = t("text.missing", { chars: missing.join(" ") });
      return;
    }
    const contours = textContours(font, text, { x: Number(textForm.x), y: Number(textForm.y), capHeight: Number(textForm.capHeight), letterSpacing: Number(textForm.letterSpacing) || 0 });
    const layerId = e.layerWithRole("engrave") ?? e.activeLayerId;
    if (e.addContours(contours, { closed: true, layerId, name: text.slice(0, 100) })) textForm.open = false;
  } catch {
    textForm.error = t("text.fontFailed");
  } finally {
    textForm.busy = false;
  }
}

// ----------------------------------------------------------------- guides
/** Drag a new guide out of a ruler: from the top ruler a horizontal one, from the left a vertical one. */
function startGuide(axis: Guide["axis"], ev: PointerEvent) {
  const e = engine.value;
  const host = stage.value;
  if (!e || !host) return;
  ev.preventDefault();
  const rect = host.getBoundingClientRect();
  const onMove = (m: PointerEvent) => {
    const [x, y] = screenToWorld(e.viewTransform, m.clientX - rect.left, m.clientY - rect.top);
    e.previewGuide = { axis, pos: e.snapAxis(axis === "x" ? x : y) };
    valueHint.value = `${axis === "x" ? "X" : "Y"} = ${formatMm(e.previewGuide.pos)} mm`;
    paintRulers();
  };
  const onUp = (u: PointerEvent) => {
    window.removeEventListener("pointermove", onMove);
    const sx = u.clientX - rect.left;
    const sy = u.clientY - rect.top;
    const preview = e.previewGuide;
    e.previewGuide = null;
    valueHint.value = "";
    // released back over a ruler or outside the canvas = cancelled
    if (preview && sx > RULER_SIZE && sy > RULER_SIZE && sx < rect.width && sy < rect.height) e.addGuide(preview.axis, preview.pos);
    paintRulers();
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp, { once: true });
}

function addGuideAt(axis: Guide["axis"]) {
  const pos = Number(axis === "x" ? guideForm.x : guideForm.y);
  if (Number.isFinite(pos)) engine.value?.addGuide(axis, pos);
}

function setGuidePos(index: number, ev: Event) {
  const pos = Number((ev.target as HTMLInputElement).value);
  if (Number.isFinite(pos)) engine.value?.moveGuide(index, pos);
}

// --------------------------------------------------------------- keyboard
/**
 * Paper.js cancels the canvas mousedown, so the browser keeps the focus in the last edited field
 * (grid step, symmetry axis, typed length…) and shortcuts — Enter to finish a path, tool keys —
 * would type into that field. A click in the drawing gives the keyboard back to the editor.
 */
function releaseFieldFocus() {
  const el = document.activeElement as HTMLElement | null;
  if (el && el !== document.body && el.closest("input, select, textarea")) el.blur();
}

function isTyping(ev: KeyboardEvent) {
  const el = ev.target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

const TOOL_KEYS: Record<string, ToolName> = { v: "select", n: "node", p: "pen", r: "rect", e: "ellipse", l: "line", g: "polygon", a: "arc", d: "dimension", m: "measure", h: "pan" };

function onKeyDown(ev: KeyboardEvent) {
  const e = engine.value;
  if (!e) return;
  // a dialog is open: Esc closes it (even from a field inside), nothing else reaches the canvas
  if (shortcutsOpen.value || planOpen.value || calib.open || persp.open || holes.open || textForm.open || library.open) {
    if (ev.key === "Escape") {
      ev.preventDefault();
      shortcutsOpen.value = false;
      planOpen.value = false;
      calib.open = false;
      persp.open = false;
      holes.open = false;
      textForm.open = false;
      library.open = false;
    }
    return;
  }
  if (isTyping(ev)) return;
  if (ev.key === "?") {
    ev.preventDefault();
    shortcutsOpen.value = true;
    return;
  }
  const mod = ev.ctrlKey || ev.metaKey;
  const key = ev.key.toLowerCase();

  if (ev.code === "Space" && !mod) {
    e.setSpace(true);
    ev.preventDefault();
    return;
  }
  if (mod) {
    const handled = (fn: () => void) => {
      ev.preventDefault();
      fn();
    };
    if (key === "z") return handled(() => (ev.shiftKey ? e.redo() : e.undo()));
    if (key === "y") return handled(() => e.redo());
    if (key === "s") return handled(() => void save());
    if (key === "c") return handled(() => e.copySelection());
    if (key === "x") return handled(() => e.cutSelection());
    if (key === "v") return handled(() => e.pasteClipboard());
    if (key === "d") return handled(() => e.duplicateSelection());
    if (key === "a") return handled(() => e.selectAll());
    if (key === "k") return handled(() => (ev.shiftKey ? e.breakApart() : e.combine()));
    return;
  }
  // while a pen path is open, typing a number goes to the length field (then Enter places the node)
  if (drawing.value && tool.value === "pen" && /^[0-9.,]$/.test(ev.key)) {
    ev.preventDefault();
    numeric.length = "";
    lengthInput.value?.focus();
    if (lengthInput.value) lengthInput.value.value = ev.key === "," ? "0." : ev.key;
    return;
  }
  // an active tool (pen, dimension…) gets first refusal on Enter / Escape / Backspace
  if (["Enter", "Escape", "Backspace"].includes(ev.key) && e.toolKey(ev.key)) {
    ev.preventDefault();
    return;
  }
  if (ev.key === "Delete" || ev.key === "Backspace") {
    ev.preventDefault();
    if (tool.value === "node" && sel.value.selectedNodes) e.deleteSelectedNodes();
    else e.deleteSelection();
    return;
  }
  if (ev.key.startsWith("Arrow")) {
    ev.preventDefault();
    const step = ev.shiftKey ? 10 : 1;
    const dx = ev.key === "ArrowLeft" ? -step : ev.key === "ArrowRight" ? step : 0;
    const dy = ev.key === "ArrowUp" ? -step : ev.key === "ArrowDown" ? step : 0;
    e.nudge(dx, dy);
    return;
  }
  if (key === "f") return void e.zoomToFit();
  if (key === "1") return void e.zoomActual();
  if (key === "escape") return void e.clearSelection();
  const next = TOOL_KEYS[key];
  if (next) e.setTool(next);
}

function onKeyUp(ev: KeyboardEvent) {
  if (ev.code === "Space") engine.value?.setSpace(false);
}

// --------------------------------------------------------- inspector actions
function setBound(field: "x" | "y" | "w" | "h") {
  const e = engine.value;
  if (!e || !sel.value.bounds) return;
  const patch: Record<string, number> = { [field]: Number(bounds[field]) };
  if (lockRatio.value && (field === "w" || field === "h") && sel.value.bounds.w > 0 && sel.value.bounds.h > 0) {
    const ratio = sel.value.bounds.h / sel.value.bounds.w;
    if (field === "w") patch.h = Number(bounds.w) * ratio;
    else patch.w = Number(bounds.h) / ratio;
  }
  e.setSelectionBounds(patch);
}

function applyRotation() {
  const deg = Number(rotateBy.value);
  if (!deg) return;
  engine.value?.rotateSelection(deg);
  rotateBy.value = 0;
}

async function applyOffset() {
  const e = engine.value;
  if (!e) return;
  const contours = e.selectedContours();
  if (!contours) {
    setStatus(t("hint.needTwoClosed"), true);
    return;
  }
  try {
    const result = await store.offsetContours(contours, Number(offsetForm.distance), offsetForm.join);
    e.replaceSelectionWithContours(result, offsetForm.keep);
    setStatus("");
  } catch (err) {
    setStatus(t("editor.offsetFailed", { error: errorMessage(err, t) }), true);
  }
}

function moveToLayer(ev: Event) {
  const id = (ev.target as HTMLSelectElement).value;
  if (id) engine.value?.moveSelectionToLayer(id);
}

function setName(ev: Event) {
  engine.value?.setSelectionName((ev.target as HTMLInputElement).value);
}

function applyDimension() {
  engine.value?.setDimensionProps({ offset: Number(dimForm.offset) || 0, label: dimForm.label.trim() || null });
}

function applyNodeXY() {
  engine.value?.setSingleNodePosition(Number(nodeXY.x), Number(nodeXY.y));
}

// ------------------------------------------------------------------ layers
function addLayer() {
  engine.value?.addLayer(t("editor.newLayerName"), "cut");
  refreshState();
}
function removeLayer(l: DocLayer) {
  if (!window.confirm(t("editor.layerDeleteConfirm"))) return;
  engine.value?.removeLayer(l.id);
  refreshState();
}
function patchLayer(l: DocLayer, patch: Partial<Pick<DocLayer, "name" | "role" | "visible" | "locked">>) {
  engine.value?.updateLayer(l.id, patch);
  refreshState();
}
function setActive(l: DocLayer) {
  engine.value?.setActiveLayer(l.id);
  refreshState();
}
function moveLayer(l: DocLayer, dir: -1 | 1) {
  engine.value?.moveLayer(l.id, dir);
  refreshState();
}

const activeLayerBlocked = computed(() => {
  const l = layers.value.find((x) => x.id === activeLayerId.value);
  return !l || !l.visible || l.locked;
});

// ------------------------------------------------------------- client plan
const planOpen = ref(false);
// keyboard reference, one keystroke away ("?") instead of buried in the Document tab
const shortcutsOpen = ref(false);
const shortcutItems = computed(() => t("editor.shortcutsList").split(" · "));
// keyboard focus lands in the dialog when it opens (Esc closes it)
const vFocus = { mounted: (el: HTMLElement) => el.focus() };
const planBusy = ref(false);
const planError = ref("");
const planUrl = ref("");
const planZoom = ref(false);
const planForm = reactive({ paper: "A4", scale: "", customer: "", order_ref: "", title: "", notes: "" });

async function openPlan() {
  if (unsaved.value && !(await save())) return;
  planForm.title ||= meta.name;
  planOpen.value = true;
  await refreshPlan();
}

// the preview follows the form: no "refresh" button to remember
let planTimer: ReturnType<typeof setTimeout> | undefined;
watch(
  () => ({ ...planForm }),
  () => {
    if (!planOpen.value) return;
    clearTimeout(planTimer);
    planTimer = setTimeout(() => void refreshPlan(), 350);
  },
);

function onPlanKey(ev: KeyboardEvent) {
  if (ev.key === "Escape") {
    ev.preventDefault();
    planOpen.value = false;
  }
}

function planParams() {
  return {
    paper: planForm.paper,
    scale: planForm.scale ? Number(planForm.scale) : undefined,
    customer: planForm.customer.trim(),
    order_ref: planForm.order_ref.trim(),
    title: planForm.title.trim(),
    notes: planForm.notes.trim(),
  };
}

async function refreshPlan() {
  planBusy.value = true;
  planError.value = "";
  try {
    const blob = await store.designPlan(designId.value, planParams());
    if (planUrl.value) URL.revokeObjectURL(planUrl.value);
    planUrl.value = URL.createObjectURL(blob);
  } catch (err) {
    planError.value = t("plan.failed", { error: errorMessage(err, t) });
  } finally {
    planBusy.value = false;
  }
}

async function downloadPlan() {
  try {
    const blob = await store.designPlan(designId.value, planParams(), true);
    saveBlob(blob, `plan_${meta.name.replace(/[^\w.-]+/g, "_")}.svg`);
  } catch (err) {
    planError.value = t("plan.failed", { error: errorMessage(err, t) });
  }
}

function printPlan() {
  if (!planUrl.value) return;
  const w = window.open(planUrl.value, "_blank");
  if (w) w.addEventListener("load", () => w.print());
}

// ------------------------------------------------------------------- misc
const roleColor = (role: LayerRole) => ROLE_STYLE[role].stroke;
const cursorText = computed(() => `${formatMm(cursor.value[0])}, ${formatMm(cursor.value[1])} mm`);
const toolLabel = (name: ToolName) => t(`tool.${name}`);
</script>

<template>
  <div class="h-[calc(100vh-56px)] flex flex-col bg-slate-100">
    <p v-if="loadError" class="p-6 text-red-600 text-sm">{{ loadError }}</p>

    <template v-else>
      <!-- top bar -->
      <div class="bg-paper border-b border-slate-200 px-3 py-2 flex items-center gap-2 flex-wrap text-sm">
        <router-link to="/designs" class="text-slate-500 hover:text-slate-900">← {{ t("editor.back") }}</router-link>
        <input
          v-model="meta.name"
          :aria-label="t('common.name')"
          class="font-semibold text-slate-900 border border-transparent hover:border-slate-300 focus:border-accent-500 rounded px-2 py-1 w-56"
        />
        <span v-if="unsaved" class="text-amber-700 text-xs">● {{ t("editor.unsaved") }}</span>
        <span v-else class="text-green-700 text-xs">✓ {{ t("editor.saved") }}</span>
        <!-- the link the nesting relies on: model + material, in plain sight -->
        <select v-model.number="meta.knife_model_id" :aria-label="t('designs.knifeModel')" :title="t('designs.knifeModel')" class="max-w-40 input-sm px-1.5 py-1 text-xs text-slate-700">
          <option :value="0">{{ t("editor.noModel") }}</option>
          <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
        </select>
        <select v-model.number="meta.material_id" :aria-label="t('designs.material')" :title="t('designs.material')" class="max-w-40 input-sm px-1.5 py-1 text-xs text-slate-700">
          <option :value="0">{{ t("editor.noMaterial") }}</option>
          <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
        </select>
        <div class="flex-1"></div>
        <button class="p-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-40" :disabled="!canUndo" :title="t('editor.undo')" :aria-label="t('editor.undo')" @click="engine?.undo()"><EditorIcon name="undo" :size="16" /></button>
        <button class="p-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-40" :disabled="!canRedo" :title="t('editor.redo')" :aria-label="t('editor.redo')" @click="engine?.redo()"><EditorIcon name="redo" :size="16" /></button>
        <button class="p-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50" :title="t('editor.fit')" :aria-label="t('editor.fit')" @click="engine?.zoomToFit()"><EditorIcon name="fit" :size="16" /></button>
        <button class="px-2 py-1 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 tabular-nums" :title="t('editor.zoomActual')" @click="engine?.zoomActual()">1:1</button>
        <input ref="fileInput" type="file" accept=".svg,image/svg+xml" class="hidden" @change="onImport" />
        <details ref="exportMenu" class="relative">
          <summary class="list-none cursor-pointer select-none flex items-center gap-1 px-2 py-1 rounded-md border border-slate-300 bg-paper text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors">
            {{ t("editor.file") }} <EditorIcon name="chevron-down" :size="14" />
          </summary>
          <div class="absolute right-0 z-30 mt-1 w-72 bg-paper border border-slate-200 rounded-lg shadow-lg py-1">
            <button class="block w-full text-left px-3 py-1.5 hover:bg-slate-50" @click="importFrom">{{ t("editor.importSvg") }}</button>
            <div class="my-1 border-t border-slate-100"></div>
            <button class="block w-full text-left px-3 py-1.5 hover:bg-slate-50" @click="exportFrom('export.svg')">{{ t("editor.exportSvg") }}</button>
            <button class="block w-full text-left px-3 py-1.5 hover:bg-slate-50" @click="exportFrom('export.dxf')">{{ t("editor.exportDxf") }}</button>
            <div class="my-1 border-t border-slate-100"></div>
            <div class="px-3 py-1.5 space-y-2 text-xs text-slate-600" @click.stop>
              <label class="flex items-center gap-2"><input v-model="exportOpts.arcs" type="checkbox" /> {{ t("export.arcs") }}</label>
              <label class="flex items-center justify-between gap-2">{{ t("export.kerf") }}
                <input v-model.number="exportOpts.kerf" type="number" min="0" max="3" step="0.01" class="input-sm w-20 text-right" />
              </label>
              <p class="leading-snug text-slate-500">{{ exportOpts.kerf ? t("export.kerfOn", { half: String((Number(exportOpts.kerf) || 0) / 2).replace(".", ",") }) : t("export.kerfOff") }}</p>
            </div>
          </div>
        </details>
        <button class="px-2 py-1 rounded border border-slate-300 text-slate-700 hover:bg-slate-50" @click="openPlan">{{ t("editor.plan") }}</button>
        <button
          class="btn btn-primary btn-sm"
          :disabled="saving || !unsaved"
          @click="save"
        >
          {{ saving ? t("editor.saving") : t("editor.save") }}
        </button>
      </div>

      <!-- options bar -->
      <div class="bg-paper border-b border-slate-200 px-3 py-1.5 flex items-center gap-4 flex-wrap text-xs text-slate-600">
        <label class="flex items-center gap-1"><input v-model="snapOpts.grid" type="checkbox" /> {{ t("editor.snapGrid") }}</label>
        <label class="flex items-center gap-1"><input v-model="snapOpts.nodes" type="checkbox" /> {{ t("editor.snapNodes") }}</label>
        <label class="flex items-center gap-1">
          {{ t("editor.gridSize") }}
          <input v-model.number="opts.gridSize" type="number" min="0.01" max="1000" step="any" list="grid-presets" class="w-16 input-sm px-1 py-0.5 text-xs" />
          <datalist id="grid-presets"><option v-for="g in [0.1, 0.25, 0.5, 1, 2, 5, 10, 25]" :key="g" :value="g"></option></datalist>
        </label>
        <label class="flex items-center gap-1"><input v-model="opts.showGrid" type="checkbox" /> {{ t("editor.showGrid") }}</label>
        <details class="relative">
          <summary class="cursor-pointer select-none text-slate-700 inline-flex items-center gap-1"><EditorIcon name="magnet" :size="14" /> {{ t("editor.snapMenu") }}</summary>
          <div class="absolute z-20 mt-1 w-72 bg-paper border border-slate-200 rounded-lg shadow-lg p-3 space-y-1">
            <label v-for="k in snapKinds" :key="k" class="flex items-center gap-2"><input v-model="snapOpts[k]" type="checkbox" /> {{ t(`snap.opt.${k}`) }}</label>
            <label class="flex items-center gap-2 pt-1">{{ t("editor.snapRadius") }}
              <input v-model.number="opts.snapRadius" type="number" min="2" max="40" class="w-14 input-sm px-1 py-0.5 text-xs" />
            </label>
            <p class="text-xs text-slate-500 pt-1">{{ t("snap.help") }}</p>
          </div>
        </details>
        <label v-if="tool === 'rect'" class="flex items-center gap-1">
          {{ t("editor.cornerRadius") }}
          <input v-model.number="opts.cornerRadius" type="number" min="0" step="0.5" class="w-16 input-sm px-1 py-0.5 text-xs" />
        </label>
        <template v-if="tool === 'pen'">
          <label class="flex items-center gap-1">{{ t("sym.label") }}
            <select v-model="symmetry.axis" class="input-sm px-1 py-0.5 text-xs">
              <option value="">{{ t("sym.none") }}</option>
              <option value="x">{{ t("sym.vertical") }}</option>
              <option value="y">{{ t("sym.horizontal") }}</option>
            </select>
          </label>
          <label v-if="symmetry.axis" class="flex items-center gap-1">{{ symmetry.axis === "x" ? "X =" : "Y =" }}
            <input v-model.number="symmetry.pos" type="number" step="any" class="w-16 input-sm px-1 py-0.5 text-xs" />
          </label>
          <span v-if="drawing" class="flex items-center gap-1 bg-accent-50 border border-accent-200 rounded px-2 py-0.5">
            {{ t("num.length") }}
            <input ref="lengthInput" v-model.number="numeric.length" type="number" min="0" step="any" class="w-16 input-sm px-1 py-0.5 text-xs" @keydown.enter.prevent="applyNumeric" @keydown.esc.prevent="cancelNumeric" />
            {{ t("num.angle") }}
            <input v-model.number="numeric.angle" type="number" step="any" class="w-14 input-sm px-1 py-0.5 text-xs" @keydown.enter.prevent="applyNumeric" />
            <button class="px-1.5 rounded bg-accent-600 text-white text-xs" @click="applyNumeric">{{ t("num.apply") }}</button>
          </span>
        </template>
        <label v-if="tool === 'polygon'" class="flex items-center gap-1">
          {{ t("editor.polygonSides") }}
          <input v-model.number="opts.polygonSides" type="number" min="3" max="64" class="w-16 input-sm px-1 py-0.5 text-xs" />
        </label>
        <span v-if="activeLayerBlocked" class="inline-flex items-center gap-1 text-amber-700"><EditorIcon name="warning" :size="14" /> {{ t("editor.layerLockedHint") }}</span>
      </div>

      <div class="flex-1 flex min-h-0">
        <!-- toolbar -->
        <div class="w-12 bg-paper border-r border-slate-200 flex flex-col items-center py-2 gap-1">
          <button
            v-for="name in tools"
            :key="name"
            class="w-9 h-9 rounded-lg flex items-center justify-center"
            :class="tool === name ? 'bg-accent-600 text-white' : 'text-slate-600 hover:bg-slate-100'"
            :title="toolLabel(name)"
            :aria-label="toolLabel(name)"
            :aria-pressed="tool === name"
            @click="engine?.setTool(name)"
          >
            <EditorIcon :name="name" />
          </button>
          <div class="w-7 border-t border-slate-200 my-1"></div>
          <button class="w-9 h-9 rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-100" :title="t('library.title')" :aria-label="t('library.title')" @click="openLibrary"><EditorIcon name="library" /></button>
          <button class="w-9 h-9 rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-100" :title="t('holes.title')" :aria-label="t('holes.title')" @click="openHoles"><EditorIcon name="holes" /></button>
          <button class="w-9 h-9 rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-100" :title="t('text.title')" :aria-label="t('text.title')" @click="openText"><EditorIcon name="text" /></button>
        </div>

        <!-- canvas stack -->
        <div ref="stage" class="flex-1 relative overflow-hidden min-w-0">
          <canvas ref="gridCanvas" class="absolute inset-0 pointer-events-none"></canvas>
          <canvas ref="paperCanvas" class="absolute inset-0" style="touch-action: none" @pointerdown="releaseFieldFocus"></canvas>
          <canvas ref="rulerCanvas" class="absolute inset-0 pointer-events-none"></canvas>
          <!-- drag a guide out of a ruler -->
          <div class="absolute top-0 right-0 cursor-row-resize" :style="{ left: `${RULER_SIZE}px`, height: `${RULER_SIZE}px` }" @pointerdown="startGuide('y', $event)"></div>
          <div class="absolute left-0 bottom-0 cursor-col-resize" :style="{ top: `${RULER_SIZE}px`, width: `${RULER_SIZE}px` }" @pointerdown="startGuide('x', $event)"></div>
          <p v-if="!design && !loadError" class="absolute inset-0 flex items-center justify-center text-sm text-slate-500">{{ t("editor.loading") }}</p>
        </div>

        <!-- right panel -->
        <aside class="w-80 bg-paper border-l border-slate-200 flex flex-col min-h-0">
          <div class="flex border-b border-slate-200 text-sm">
            <button
              v-for="id in ['object', 'layers', 'background', 'document'] as const"
              :key="id"
              class="flex-1 py-2"
              :class="tab === id ? 'border-b-2 border-accent-600 text-slate-900 font-medium' : 'border-b-2 border-transparent text-slate-500 hover:text-slate-800'"
              @click="tab = id"
            >
              {{ t(`editor.tab.${id}`) }}
            </button>
          </div>

          <div class="flex-1 overflow-y-auto p-3 space-y-4 text-sm">
            <!-- OBJECT TAB -->
            <template v-if="tab === 'object'">
              <div v-if="tool === 'measure'" class="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs text-slate-700 space-y-0.5" aria-live="polite">
                <p class="font-medium text-slate-900">{{ t("measure.title") }}</p>
                <template v-if="measurement">
                  <p>{{ t("measure.distance") }} : <b class="font-mono">{{ formatMm(measurement.distance) }} mm</b></p>
                  <p class="font-mono">ΔX {{ formatMm(measurement.dx) }} · ΔY {{ formatMm(measurement.dy) }} mm</p>
                  <p>{{ t("measure.angle") }} : <span class="font-mono">{{ measurement.angle }}°</span></p>
                  <button class="mt-1 w-full btn btn-outline btn-sm" @click="engine?.measurementToDimension()">{{ t("measure.toDimension") }}</button>
                </template>
                <p v-else class="text-slate-500">{{ t("measure.empty") }}</p>
              </div>
              <p v-if="!sel.count" class="text-slate-500 text-xs">{{ t("editor.nothingSelected") }}</p>

              <template v-else>
                <p class="text-xs text-slate-500">{{ t("editor.selectedCount", { n: sel.count }) }}</p>

                <div v-if="sel.count === 1">
                  <label class="field-label" for="designeditor-f1">{{ t("editor.objectName") }}</label>
                  <input id="designeditor-f1" :value="sel.name ?? ''" class="input-sm w-full" @change="setName" />
                </div>

                <div>
                  <label class="field-label" for="designeditor-f2">{{ t("editor.layer") }}</label>
                  <select id="designeditor-f2" :value="sel.layerId ?? ''" class="input-sm w-full" @change="moveToLayer">
                    <option v-if="sel.mixedLayers" value="">{{ t("editor.mixedLayers") }}</option>
                    <option v-for="l in layers" :key="l.id" :value="l.id">{{ l.name }}</option>
                  </select>
                </div>

                <div>
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-slate-500">{{ t("editor.position") }}</span>
                    <label class="text-xs text-slate-500 flex items-center gap-1"><input v-model="lockRatio" type="checkbox" /> {{ t("editor.lockRatio") }}</label>
                  </div>
                  <div class="grid grid-cols-2 gap-2">
                    <label class="text-xs text-slate-500">X <input v-model.number="bounds.x" type="number" step="any" class="input-sm w-full" @change="setBound('x')" /></label>
                    <label class="text-xs text-slate-500">Y <input v-model.number="bounds.y" type="number" step="any" class="input-sm w-full" @change="setBound('y')" /></label>
                    <label class="text-xs text-slate-500">L <input v-model.number="bounds.w" type="number" step="any" min="0" class="input-sm w-full" @change="setBound('w')" /></label>
                    <label class="text-xs text-slate-500">H <input v-model.number="bounds.h" type="number" step="any" min="0" class="input-sm w-full" @change="setBound('h')" /></label>
                  </div>
                </div>

                <label class="block text-xs text-slate-500">{{ t("editor.rotateBy") }}
                  <input v-model.number="rotateBy" type="number" step="any" class="input-sm w-full" @keydown.enter="applyRotation" @change="applyRotation" />
                </label>

                <div>
                  <p class="text-xs text-slate-500 mb-1">{{ t("editor.transform") }}</p>
                  <div class="grid grid-cols-6 gap-1">
                    <button v-for="tr in transforms" :key="tr.key" class="h-8 rounded-md border border-slate-300 bg-paper text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors flex items-center justify-center" :title="t(tr.label)" :aria-label="t(tr.label)" @click="tr.run()">
                      <EditorIcon :name="tr.icon" :size="18" />
                    </button>
                  </div>
                </div>

                <div v-if="sel.count > 1">
                  <p class="text-xs text-slate-500 mb-1">{{ t("editor.align") }}</p>
                  <div class="grid grid-cols-3 gap-1">
                    <button v-for="k in alignKinds" :key="k" class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.align(k)">{{ t(`editor.align.${k}`) }}</button>
                  </div>
                  <div v-if="sel.count > 2" class="grid grid-cols-2 gap-1 mt-1">
                    <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.distribute('h')">{{ t("editor.distributeH") }}</button>
                    <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.distribute('v')">{{ t("editor.distributeV") }}</button>
                  </div>
                </div>

                <div v-if="sel.count > 1">
                  <p class="text-xs text-slate-500 mb-1">{{ t("editor.boolean") }}</p>
                  <div class="grid grid-cols-2 gap-1">
                    <button v-for="op in booleanOps" :key="op" class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.booleanOp(op)">{{ t(`editor.boolean.${op}`) }}</button>
                    <button class="col-span-2 px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.combine()">{{ t("editor.combine") }}</button>
                  </div>
                  <p class="text-xs text-slate-500 mt-1">{{ t("editor.booleanHelp") }}</p>
                </div>
                <button v-else-if="sel.path?.compound" class="w-full px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.breakApart()">{{ t("editor.breakApart") }}</button>

                <div v-if="sel.path" class="bg-slate-100 rounded-lg p-2 text-xs text-slate-600 space-y-0.5">
                  <p class="font-medium text-slate-700">{{ t("editor.shapeInfo") }}</p>
                  <p>{{ sel.path.closed ? t("editor.closedShape") : t("editor.openPath") }}</p>
                  <p>{{ t("editor.nodeCount") }} : {{ sel.path.nodeCount }}</p>
                  <p v-if="sel.path.closed">{{ t("editor.area") }} : {{ formatMm(sel.path.area) }} mm² ({{ formatMm(sel.path.area / 100) }} cm²)</p>
                  <p>{{ t("editor.perimeter") }} : {{ formatMm(sel.path.perimeter) }} mm</p>
                </div>

                <div v-if="sel.path && sel.path.closed" class="space-y-2">
                  <p class="text-xs font-medium text-slate-700">{{ t("editor.offsetTitle") }}</p>
                  <label class="field-label">{{ t("editor.offsetDistance") }}
                    <input v-model.number="offsetForm.distance" type="number" step="0.1" class="input-sm w-full" />
                  </label>
                  <label class="field-label">{{ t("editor.offsetJoin") }}
                    <select v-model="offsetForm.join" class="input-sm w-full">
                      <option value="round">{{ t("editor.offsetJoin.round") }}</option>
                      <option value="mitre">{{ t("editor.offsetJoin.mitre") }}</option>
                      <option value="bevel">{{ t("editor.offsetJoin.bevel") }}</option>
                    </select>
                  </label>
                  <label class="text-xs text-slate-500 flex items-center gap-1"><input v-model="offsetForm.keep" type="checkbox" /> {{ t("editor.offsetKeep") }}</label>
                  <button class="w-full px-2 py-1 rounded border border-accent-300 text-accent-700 bg-accent-50" @click="applyOffset">{{ t("editor.offsetApply") }}</button>
                </div>

                <div v-if="sel.dimension" class="space-y-2">
                  <p class="text-xs font-medium text-slate-700">{{ t("editor.dimTitle") }}</p>
                  <p class="text-xs text-slate-500">{{ t("editor.dimLength") }} : {{ formatMm(sel.dimension.length) }} mm</p>
                  <label class="field-label">{{ t("editor.dimOffset") }}
                    <input v-model.number="dimForm.offset" type="number" step="any" class="input-sm w-full" @change="applyDimension" />
                  </label>
                  <label class="field-label">{{ t("editor.dimLabel") }}
                    <input v-model="dimForm.label" class="input-sm w-full" @change="applyDimension" />
                  </label>
                </div>
                <button class="w-full mt-1 py-1.5 rounded-md text-sm text-red-700 hover:bg-red-50 flex items-center justify-center gap-1.5" @click="engine?.deleteSelection()">
                  <EditorIcon name="close" :size="14" /> {{ t("editor.delete") }}
                </button>
              </template>

              <div v-if="tool === 'node' || sel.selectedNodes" class="space-y-2 border-t border-slate-100 pt-3">
                <p class="text-xs font-medium text-slate-700">{{ t("editor.nodesTitle") }}</p>
                <p class="text-xs text-slate-500">{{ t("editor.nodesSelected", { n: sel.selectedNodes }) }}</p>
                <div v-if="sel.singleNode" class="grid grid-cols-2 gap-2">
                  <label class="text-xs text-slate-500">{{ t("editor.nodeX") }} <input v-model.number="nodeXY.x" type="number" step="any" class="input-sm w-full" @change="applyNodeXY" /></label>
                  <label class="text-xs text-slate-500">{{ t("editor.nodeY") }} <input v-model.number="nodeXY.y" type="number" step="any" class="input-sm w-full" @change="applyNodeXY" /></label>
                </div>
                <div class="grid grid-cols-2 gap-1">
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.deleteSelectedNodes()">{{ t("editor.nodeDelete") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.insertNodes()">{{ t("editor.nodeInsert") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.setNodeType('smooth')">{{ t("editor.nodeSmooth") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.setNodeType('corner')">{{ t("editor.nodeCorner") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.toggleClosed()">{{ t("editor.nodeToggleClosed") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.reversePaths()">{{ t("editor.nodeReverse") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.simplifyPaths()">{{ t("editor.nodeSimplify") }}</button>
                  <button class="px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="engine?.flattenPaths()">{{ t("editor.nodeFlatten") }}</button>
                </div>
                <div class="space-y-1">
                  <p class="text-xs font-medium text-slate-700">{{ t("corner.title") }}</p>
                  <div class="flex items-center gap-1">
                    <input v-model.number="cornerSize" type="number" min="0" step="any" class="w-16 input-sm px-1 py-0.5 text-xs text-sm" />
                    <span class="text-xs text-slate-500">mm</span>
                    <button class="flex-1 px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="roundCorners('fillet')">{{ t("corner.fillet") }}</button>
                    <button class="flex-1 px-1 py-1 rounded-md border border-slate-300 bg-paper text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" @click="roundCorners('chamfer')">{{ t("corner.chamfer") }}</button>
                  </div>
                  <p class="text-xs text-slate-500">{{ t("corner.help") }}</p>
                </div>
              </div>
            </template>

            <!-- LAYERS TAB -->
            <template v-else-if="tab === 'layers'">
              <p class="text-xs text-slate-500">{{ t("editor.layersHelp") }}</p>
              <div class="space-y-2">
                <div
                  v-for="(l, i) in [...layers].reverse()"
                  :key="l.id"
                  class="border rounded-lg p-2 space-y-1"
                  :class="l.id === activeLayerId ? 'border-accent-400 bg-accent-50/40' : 'border-slate-200'"
                >
                  <div class="flex items-center gap-1">
                    <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ background: roleColor(l.role) }"></span>
                    <input :value="l.name" class="flex-1 min-w-0 border border-transparent hover:border-slate-300 rounded px-1 py-0.5" @change="patchLayer(l, { name: ($event.target as HTMLInputElement).value })" />
                    <button :title="t('editor.layerVisible')" :aria-label="t('editor.layerVisible')" :aria-pressed="l.visible" class="p-0.5 rounded hover:bg-slate-100" :class="l.visible ? 'text-slate-700' : 'text-slate-400'" @click="patchLayer(l, { visible: !l.visible })"><EditorIcon :name="l.visible ? 'eye' : 'eye-off'" :size="16" /></button>
                    <button :title="t('editor.layerLocked')" :aria-label="t('editor.layerLocked')" :aria-pressed="l.locked" class="p-0.5 rounded hover:bg-slate-100" :class="l.locked ? 'text-slate-800' : 'text-slate-400'" @click="patchLayer(l, { locked: !l.locked })"><EditorIcon :name="l.locked ? 'lock' : 'unlock'" :size="16" /></button>
                  </div>
                  <div class="flex items-center gap-1">
                    <select :value="l.role" class="flex-1 min-w-0 input-sm px-1 py-0.5 text-xs text-xs" @change="patchLayer(l, { role: ($event.target as HTMLSelectElement).value as LayerRole })">
                      <option v-for="r in roles" :key="r" :value="r">{{ t(`editor.role.${r}`) }}</option>
                    </select>
                    <button class="p-0.5 rounded text-slate-500 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30" :title="t('editor.layerUp')" :aria-label="t('editor.layerUp')" :disabled="i === 0" @click="moveLayer(l, 1)"><EditorIcon name="chevron-up" :size="14" /></button>
                    <button class="p-0.5 rounded text-slate-500 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30" :title="t('editor.layerDown')" :aria-label="t('editor.layerDown')" :disabled="i === layers.length - 1" @click="moveLayer(l, -1)"><EditorIcon name="chevron-down" :size="14" /></button>
                    <button class="p-0.5 rounded text-slate-400 hover:text-red-700 hover:bg-slate-100 disabled:opacity-30" :title="t('editor.layerDelete')" :aria-label="t('editor.layerDelete')" :disabled="layers.length <= 1" @click="removeLayer(l)"><EditorIcon name="close" :size="14" /></button>
                  </div>
                  <button
                    class="text-xs"
                    :class="l.id === activeLayerId ? 'text-accent-700 font-medium' : 'text-slate-500 hover:text-slate-800'"
                    :aria-pressed="l.id === activeLayerId"
                    :title="t('editor.layerActive')"
                    @click="setActive(l)"
                  >
                    {{ l.id === activeLayerId ? `● ${t("editor.layerIsActive")}` : `○ ${t("editor.layerMakeActive")}` }}
                  </button>
                </div>
              </div>
              <button class="w-full px-2 py-1 rounded border border-slate-300" @click="addLayer">+ {{ t("editor.addLayer") }}</button>
            </template>

            <!-- BACKGROUND TAB -->
            <template v-else-if="tab === 'background'">
              <p class="text-xs font-medium text-slate-700">{{ t("bg.title") }}</p>
              <p class="text-xs text-slate-500">{{ t("bg.intro") }}</p>
              <template v-if="!bg">
                <button class="w-full px-2 py-1.5 rounded-lg bg-accent-600 text-white" @click="pickBackground">{{ t("bg.import") }}</button>
              </template>
              <template v-else>
                <div class="flex items-center gap-3 text-xs">
                  <label class="flex items-center gap-1"><input type="checkbox" :checked="bg.visible" @change="engine?.updateBackground({ visible: ($event.target as HTMLInputElement).checked })" /> {{ t("bg.visible") }}</label>
                  <label class="flex items-center gap-1 flex-1">{{ t("bg.opacity") }}
                    <input type="range" min="5" max="100" :value="Math.round(bg.opacity * 100)" class="flex-1" @input="engine?.updateBackground({ opacity: Number(($event.target as HTMLInputElement).value) / 100 })" />
                  </label>
                </div>
                <button class="w-full btn btn-outline btn-sm" @click="engine?.setTool('calibrate')"><EditorIcon name="measure" :size="16" /> {{ t("bg.calibrate") }}</button>
                <button class="w-full btn btn-outline btn-sm" :title="t('persp.help')" @click="engine?.setTool('perspective')"><EditorIcon name="fit" :size="16" /> {{ t("bg.perspective") }}</button>
                <button v-if="bgBeforeRectify" class="w-full btn btn-outline btn-sm" @click="undoPerspective"><EditorIcon name="undo" :size="16" /> {{ t("persp.undo") }}</button>
                <div class="rounded-lg p-2 text-xs space-y-1" :class="bg.calibrated ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800'">
                  <p>{{ bg.calibrated ? `✓ ${t("bg.calibrated")}` : `⚠ ${t("bg.notCalibrated")}` }}</p>
                  <p v-if="bg.calibrated && bgResolution">{{ t("bg.resolution", { mm: formatMm(bgResolution) }) }}</p>
                  <p v-if="bg.calibrated && bgResolution && bgResolution > 0.1" class="text-amber-700">{{ t("bg.resolutionWarn") }}</p>
                </div>
                <div>
                  <p class="text-xs text-slate-500 mb-1">{{ t("bg.placement") }}</p>
                  <div class="grid grid-cols-2 gap-2">
                    <label class="text-xs text-slate-500">{{ t("bg.centerX") }} <input :value="bg.cx" type="number" step="any" class="input-sm w-full" @change="setBgField('cx', $event)" /></label>
                    <label class="text-xs text-slate-500">{{ t("bg.centerY") }} <input :value="bg.cy" type="number" step="any" class="input-sm w-full" @change="setBgField('cy', $event)" /></label>
                    <label class="text-xs text-slate-500">{{ t("bg.width") }} <input :value="bg.width_mm" type="number" step="any" min="0" class="input-sm w-full" @change="setBgField('width_mm', $event)" /></label>
                    <label class="text-xs text-slate-500">{{ t("bg.height") }} <input :value="bg.height_mm" type="number" step="any" min="0" class="input-sm w-full" @change="setBgField('height_mm', $event)" /></label>
                    <label class="text-xs text-slate-500 col-span-2">{{ t("bg.rotation") }} <input :value="bg.rotation_deg" type="number" step="any" class="input-sm w-full" @change="setBgField('rotation_deg', $event)" /></label>
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <button class="px-2 py-1 rounded border border-slate-300 text-xs" @click="pickBackground">{{ t("bg.replace") }}</button>
                  <button class="px-2 py-1 rounded border border-red-300 text-red-600 text-xs" @click="removeBackground">{{ t("bg.remove") }}</button>
                </div>
              </template>
              <div class="bg-slate-50 rounded-lg p-2 text-xs text-slate-600">
                <p class="font-medium text-slate-700 mb-1">{{ t("bg.tipsTitle") }}</p>
                <p>{{ t("bg.tips") }}</p>
              </div>
              <input ref="bgInput" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="onBackgroundFile" />
            </template>

            <!-- DOCUMENT TAB -->
            <template v-else>
              <div>
                <label class="field-label" for="designeditor-f3">{{ t("editor.docKind") }}</label>
                <select id="designeditor-f3" v-model="meta.kind" class="input-sm w-full">
                  <option v-for="k in kinds" :key="k" :value="k">{{ t(`designs.kind.${k}`) }}</option>
                </select>
              </div>
              <div>
                <label class="field-label" for="designeditor-f4">{{ t("designs.knifeModel") }}</label>
                <select id="designeditor-f4" v-model.number="meta.knife_model_id" class="input-sm w-full">
                  <option :value="0">{{ t("designs.none") }}</option>
                  <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="field-label" for="designeditor-f5">{{ t("designs.material") }}</label>
                <select id="designeditor-f5" v-model.number="meta.material_id" class="input-sm w-full">
                  <option :value="0">{{ t("designs.none") }}</option>
                  <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="field-label" for="designeditor-f6">{{ t("editor.docNotes") }}</label>
                <textarea id="designeditor-f6" v-model="meta.notes" rows="3" class="input-sm w-full"></textarea>
              </div>
              <div v-if="design" class="bg-slate-50 rounded-lg p-2 text-xs text-slate-600 space-y-0.5">
                <p class="font-medium text-slate-700">{{ t("editor.docMetrics") }}</p>
                <p>{{ num(design.width_mm) }} × {{ num(design.height_mm) }} mm</p>
                <p>{{ t("editor.area") }} : {{ num(design.area_mm2 / 100, 2) }} cm²</p>
                <p>{{ t("editor.perimeter") }} : {{ num(design.perimeter_mm) }} mm</p>
                <p>{{ t("editor.docParts") }} : {{ design.part_count }}</p>
                <p class="text-slate-500">{{ t("editor.docMetricsHint") }}</p>
              </div>
              <div class="space-y-2 border-t border-slate-100 pt-3">
                <p class="text-xs font-medium text-slate-700">{{ t("guides.title") }}</p>
                <p class="text-xs text-slate-500">{{ t("guides.help") }}</p>
                <p v-if="!guides.length" class="text-xs text-slate-500">{{ t("guides.none") }}</p>
                <div v-for="(g, i) in guides" :key="i" class="flex items-center gap-1 text-xs">
                  <span class="w-28 text-slate-500">{{ g.axis === "x" ? t("guides.vertical") : t("guides.horizontal") }}</span>
                  <input :value="g.pos" type="number" step="any" class="flex-1 min-w-0 input-sm px-1 py-0.5 text-xs" @change="setGuidePos(i, $event)" />
                  <button class="p-0.5 rounded text-slate-400 hover:text-red-700 hover:bg-slate-100" :aria-label="t('common.delete')" @click="engine?.removeGuide(i)"><EditorIcon name="close" :size="14" /></button>
                </div>
                <div class="grid grid-cols-2 gap-1 text-xs">
                  <input v-model.number="guideForm.x" type="number" step="any" class="input-sm px-1 py-0.5 text-xs" />
                  <button class="px-1 py-0.5 rounded border border-slate-300" @click="addGuideAt('x')">{{ t("guides.addV") }}</button>
                  <input v-model.number="guideForm.y" type="number" step="any" class="input-sm px-1 py-0.5 text-xs" />
                  <button class="px-1 py-0.5 rounded border border-slate-300" @click="addGuideAt('y')">{{ t("guides.addH") }}</button>
                </div>
                <button v-if="guides.length" class="text-xs text-red-600" @click="engine?.clearGuides()">{{ t("guides.clear") }}</button>
              </div>
              <div class="text-xs text-slate-500">
                <p class="font-medium text-slate-700 mb-1">{{ t("editor.shortcuts") }}</p>
                <p>{{ t("editor.shortcutsList") }}</p>
              </div>
            </template>
          </div>
        </aside>
      </div>

      <!-- status bar -->
      <div class="bg-paper border-t border-slate-200 px-3 py-1 text-xs text-slate-500 flex items-center gap-4">
        <span class="flex-1 truncate">{{ hintText }}</span>
        <span v-if="valueHint" class="font-mono text-accent-600">{{ valueHint }}</span>
        <span v-if="status" :class="statusIsError ? 'text-red-600' : 'text-green-700'">{{ status }}</span>
        <span>{{ t("editor.cursor") }} : {{ cursorText }}</span>
        <span>{{ t("editor.zoom") }} : {{ zoomPct }} %</span>
        <button class="ml-3 w-5 h-5 rounded-full border border-slate-300 text-slate-600 hover:text-slate-900 hover:border-slate-400 leading-none" :title="t('editor.shortcutsOpen')" :aria-label="t('editor.shortcutsOpen')" @click="shortcutsOpen = true">?</button>
      </div>
    </template>

    <!-- shape library dialog -->
    <div v-if="library.open" class="fixed inset-0 bg-black/45 backdrop-blur-[1px] z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" @click.self="library.open = false">
      <form class="bg-paper rounded-xl shadow-xl w-full max-w-2xl p-4 space-y-3 text-sm" @submit.prevent="insertLibrary">
        <div class="flex items-center gap-3">
          <h2 class="sheet-title flex-1">{{ t("library.title") }}</h2>
          <div class="flex rounded-lg border border-slate-300 overflow-hidden text-xs">
            <button v-for="src in (['shapes', 'designs'] as const)" :key="src" type="button" class="px-2 py-1" :class="library.source === src ? 'bg-accent-600 text-white' : 'text-slate-600'" @click="library.source = src; centreLibraryPlacement()">{{ t(`library.${src}`) }}</button>
          </div>
        </div>
        <div class="grid grid-cols-[11rem_1fr] gap-3">
          <div class="space-y-1 max-h-80 overflow-y-auto">
            <template v-if="library.source === 'shapes'">
              <button v-for="d in SHAPES" :key="d.key" type="button" class="w-full text-left px-2 py-1 rounded" :class="library.shape === d.key ? 'bg-accent-50 text-accent-700 font-medium' : 'hover:bg-slate-50'" @click="library.shape = d.key; centreLibraryPlacement()">{{ t(d.label) }}</button>
            </template>
            <template v-else>
              <p v-if="!library.designs.length" class="text-xs text-slate-500">{{ t("library.noDesigns") }}</p>
              <button v-for="d in library.designs" :key="d.id" type="button" class="w-full text-left px-2 py-1 rounded" :class="library.designId === d.id ? 'bg-accent-50 text-accent-700 font-medium' : 'hover:bg-slate-50'" @click="pickLibraryDesign(d.id)">
                {{ d.name }}<span class="block text-xs text-slate-500">{{ t(`designs.kind.${d.kind}`) }} · {{ formatMm(d.width_mm) }} × {{ formatMm(d.height_mm) }} mm</span>
              </button>
            </template>
          </div>
          <div class="space-y-2">
            <div class="h-40 rounded-lg bg-slate-50 border border-slate-200 p-2 [&>svg]:w-full [&>svg]:h-full" v-html="libraryPreview"></div>
            <p v-if="librarySize" class="text-xs text-slate-500">{{ t("library.size", { w: formatMm(librarySize.w), h: formatMm(librarySize.h) }) }}</p>
            <p v-else-if="library.source === 'designs'" class="text-xs text-slate-500">{{ library.loading ? t("library.loading") : t("library.pick") }}</p>
            <div v-if="library.source === 'shapes'" class="grid grid-cols-2 gap-2">
              <label v-for="p in currentShape.params" :key="p.key" class="text-xs text-slate-500">{{ t(p.label) }}
                <input v-model.number="shapeValues(currentShape.key)[p.key]" type="number" :min="p.min" :max="p.max" :step="p.integer ? 1 : 'any'" class="input-sm w-full" />
              </label>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <label class="text-xs text-slate-500">{{ t("library.x") }}<input v-model.number="library.x" type="number" step="any" class="input-sm w-full" /></label>
              <label class="text-xs text-slate-500">{{ t("library.y") }}<input v-model.number="library.y" type="number" step="any" class="input-sm w-full" /></label>
            </div>
            <p class="text-xs text-slate-500">{{ t("library.help") }}</p>
          </div>
        </div>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn btn-outline btn-sm" @click="library.open = false">{{ t("common.cancel") }}</button>
          <button type="submit" class="btn btn-primary btn-sm disabled:opacity-50" :disabled="!libraryParts.length">{{ t("library.insert") }}</button>
        </div>
      </form>
    </div>

    <!-- holes dialog -->
    <div v-if="holes.open" class="fixed inset-0 bg-black/45 backdrop-blur-[1px] z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" @click.self="holes.open = false">
      <form class="bg-paper rounded-xl shadow-xl w-full max-w-sm p-4 space-y-3 text-sm" @submit.prevent="addHoles">
        <h2 class="sheet-title">{{ t("holes.title") }}</h2>
        <label class="field-label">{{ t("holes.diameter") }}
          <input v-model.number="holes.diameter" type="number" min="0.1" step="any" list="hole-sizes" required class="input-sm w-full" />
          <datalist id="hole-sizes"><option v-for="h in STANDARD_HOLES_MM" :key="h.d" :value="h.d">{{ h.label }}</option></datalist>
        </label>
        <div class="flex flex-wrap gap-1">
          <button v-for="h in STANDARD_HOLES_MM" :key="h.d" type="button" class="px-1.5 py-0.5 rounded border text-xs" :class="holes.diameter === h.d ? 'border-accent-500 bg-accent-50' : 'border-slate-300'" @click="holes.diameter = h.d">{{ h.label }}</button>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <label class="text-xs text-slate-500">{{ t("holes.x") }}<input v-model.number="holes.x" type="number" step="any" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500">{{ t("holes.y") }}<input v-model.number="holes.y" type="number" step="any" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500">{{ t("holes.count") }}<input v-model.number="holes.count" type="number" min="1" max="200" step="1" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500">{{ t("holes.pitch") }}<input v-model.number="holes.pitch" type="number" step="any" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500 col-span-2">{{ t("holes.angle") }}<input v-model.number="holes.angle" type="number" step="any" class="input-sm w-full" /></label>
        </div>
        <p class="text-xs text-slate-500">{{ t("holes.help") }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn btn-outline btn-sm" @click="holes.open = false">{{ t("common.cancel") }}</button>
          <button type="submit" class="btn btn-primary btn-sm">{{ t("holes.add") }}</button>
        </div>
      </form>
    </div>

    <!-- text dialog -->
    <div v-if="textForm.open" class="fixed inset-0 bg-black/45 backdrop-blur-[1px] z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" @click.self="textForm.open = false">
      <form class="bg-paper rounded-xl shadow-xl w-full max-w-sm p-4 space-y-3 text-sm" @submit.prevent="addText">
        <h2 class="sheet-title">{{ t("text.title") }}</h2>
        <label class="field-label">{{ t("text.text") }}
          <input v-model="textForm.text" maxlength="100" required autofocus class="input-sm w-full" />
        </label>
        <div class="grid grid-cols-2 gap-2">
          <label class="text-xs text-slate-500">{{ t("text.capHeight") }}<input v-model.number="textForm.capHeight" type="number" min="0.5" step="any" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500">{{ t("text.spacing") }}<input v-model.number="textForm.letterSpacing" type="number" step="any" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500">{{ t("text.x") }}<input v-model.number="textForm.x" type="number" step="any" class="input-sm w-full" /></label>
          <label class="text-xs text-slate-500">{{ t("text.y") }}<input v-model.number="textForm.y" type="number" step="any" class="input-sm w-full" /></label>
        </div>
        <label class="field-label">{{ t("text.font") }}
          <select v-model="textForm.weight" class="input-sm w-full">
            <option value="regular">Inter</option>
            <option value="bold">Inter {{ t("text.bold") }}</option>
            <option v-if="textForm.customName" value="custom">{{ textForm.customName }}</option>
          </select>
        </label>
        <label class="block text-xs text-accent-700 cursor-pointer">+ {{ t("text.ownFont") }}
          <input type="file" accept=".ttf,.otf,.woff,font/ttf,font/otf,font/woff" class="hidden" @change="onFontFile" />
        </label>
        <p class="text-xs text-slate-500">{{ t("text.help") }}</p>
        <p v-if="textForm.error" class="text-xs text-red-600">{{ textForm.error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn btn-outline btn-sm" @click="textForm.open = false">{{ t("common.cancel") }}</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="textForm.busy">{{ t("text.add") }}</button>
        </div>
      </form>
    </div>

    <!-- perspective dialog -->
    <div v-if="persp.open" class="fixed inset-0 bg-black/45 backdrop-blur-[1px] z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" @click.self="cancelPerspective">
      <form class="bg-paper rounded-xl shadow-xl w-full max-w-sm p-4 space-y-3 text-sm" @submit.prevent="applyPerspective">
        <h2 class="sheet-title">{{ t("persp.title") }}</h2>
        <p class="text-xs text-slate-500">{{ t("persp.intro") }}</p>
        <label class="field-label">{{ t("persp.preset") }}
          <select v-model="persp.preset" class="input-sm w-full" @change="setPerspectivePreset(persp.preset)">
            <option value="">{{ t("persp.preset.custom") }}</option>
            <option v-for="p in PERSPECTIVE_PRESETS" :key="p.key" :value="p.key">{{ t(`persp.preset.${p.key}`) }}</option>
          </select>
        </label>
        <div class="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
          <label class="text-xs text-slate-500">{{ t("persp.side12") }}
            <input v-model.number="persp.width" type="number" min="0.01" step="any" required class="input-sm w-full" />
          </label>
          <button type="button" class="px-2 py-1 rounded-md border border-slate-300 bg-paper text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors" :title="t('persp.swap')" :aria-label="t('persp.swap')" @click="[persp.width, persp.height] = [persp.height, persp.width]"><EditorIcon name="swap" :size="16" /></button>
          <label class="text-xs text-slate-500">{{ t("persp.side23") }}
            <input v-model.number="persp.height" type="number" min="0.01" step="any" required class="input-sm w-full" />
          </label>
        </div>
        <label class="flex items-center gap-2 text-xs text-slate-600"><input v-model="persp.origin" type="checkbox" /> {{ t("persp.origin") }}</label>
        <p class="text-xs text-amber-700 bg-amber-50 rounded p-2">{{ t("persp.warning") }}</p>
        <p v-if="persp.error" class="text-xs text-red-600">{{ persp.error }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn btn-outline btn-sm" @click="cancelPerspective">{{ t("common.cancel") }}</button>
          <button type="submit" class="btn btn-primary btn-sm disabled:opacity-50" :disabled="persp.busy">{{ persp.busy ? t("persp.busy") : t("persp.apply") }}</button>
        </div>
      </form>
    </div>

    <!-- calibration dialog -->
    <div v-if="calib.open" class="fixed inset-0 bg-black/45 backdrop-blur-[1px] z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" @click.self="cancelCalibration">
      <form class="bg-paper rounded-xl shadow-xl w-full max-w-sm p-4 space-y-3 text-sm" @submit.prevent="applyCalibration">
        <h2 class="sheet-title">{{ t("calib.title") }}</h2>
        <p class="text-xs text-slate-500">{{ t("calib.measured", { d: formatMm(Math.hypot(calib.b[0] - calib.a[0], calib.b[1] - calib.a[1])) }) }}</p>
        <label class="field-label">{{ t("calib.real") }}
          <input v-model.number="calib.real" type="number" min="0.01" step="any" required autofocus :placeholder="t('calib.example')" class="input-sm w-full" />
        </label>
        <label class="field-label">{{ t("calib.straighten") }}
          <select v-model="calib.straighten" class="input-sm w-full">
            <option v-for="o in ['none', 'horizontal', 'vertical']" :key="o" :value="o">{{ t(`calib.straighten.${o}`) }}</option>
          </select>
        </label>
        <label class="flex items-center gap-2 text-xs text-slate-600"><input v-model="calib.origin" type="checkbox" /> {{ t("calib.origin") }}</label>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn btn-outline btn-sm" @click="cancelCalibration">{{ t("common.cancel") }}</button>
          <button type="submit" class="btn btn-primary btn-sm">{{ t("calib.apply") }}</button>
        </div>
      </form>
    </div>

    <!-- plan modal -->
    <div v-if="shortcutsOpen" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" @click.self="shortcutsOpen = false">
      <div role="dialog" aria-modal="true" aria-labelledby="shortcuts-title" class="bg-paper rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5">
        <div class="flex items-center justify-between mb-3">
          <h2 id="shortcuts-title" class="sheet-title">{{ t("editor.shortcuts") }}</h2>
          <button v-focus class="p-1 rounded text-slate-500 hover:text-slate-900 hover:bg-slate-100" :aria-label="t('common.close')" @click="shortcutsOpen = false"><EditorIcon name="close" :size="16" /></button>
        </div>
        <ul class="grid sm:grid-cols-2 gap-x-6 gap-y-1.5 text-sm text-slate-700">
          <li v-for="item in shortcutItems" :key="item" class="border-b border-slate-100 pb-1.5">{{ item }}</li>
        </ul>
      </div>
    </div>
    <div v-if="planOpen" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" @click.self="planOpen = false" @keydown="onPlanKey">
      <div role="dialog" aria-modal="true" aria-labelledby="plan-title" class="bg-paper rounded-xl shadow-xl w-full max-w-5xl max-h-[92vh] flex flex-col md:flex-row overflow-hidden">
        <div class="md:w-72 p-5 space-y-3 overflow-y-auto border-b md:border-b-0 md:border-r border-slate-200 text-sm">
          <div class="flex items-center justify-between">
            <h2 id="plan-title" class="sheet-title">{{ t("plan.title") }}</h2>
            <button class="p-1 rounded text-slate-500 hover:text-slate-900 hover:bg-slate-100" :aria-label="t('common.close')" @click="planOpen = false"><EditorIcon name="close" :size="16" /></button>
          </div>
          <label class="field-label">{{ t("plan.paper") }}
            <select v-model="planForm.paper" v-focus class="input-sm w-full">
              <option>A4</option>
              <option>A3</option>
            </select>
          </label>
          <label class="field-label">{{ t("plan.scale") }}
            <select v-model="planForm.scale" class="input-sm w-full">
              <option value="">{{ t("plan.scaleAuto") }}</option>
              <option v-for="s in [1, 2, 0.5, 0.25, 0.2, 0.1]" :key="s" :value="String(s)">{{ s >= 1 ? `${s}:1` : `1:${Math.round(1 / s)}` }}</option>
            </select>
          </label>
          <label class="field-label">{{ t("plan.planTitle") }}<input v-model="planForm.title" class="input-sm w-full" /></label>
          <label class="field-label">{{ t("plan.customer") }}<input v-model="planForm.customer" class="input-sm w-full" /></label>
          <label class="field-label">{{ t("plan.orderRef") }}<input v-model="planForm.order_ref" class="input-sm w-full" /></label>
          <label class="field-label">{{ t("plan.notes") }}<textarea v-model="planForm.notes" rows="2" class="input-sm w-full"></textarea></label>
          <div class="pt-1 space-y-2">
            <button class="btn btn-primary w-full" :disabled="!planUrl || planBusy" @click="printPlan">{{ t("plan.print") }}</button>
            <button class="btn btn-outline btn-sm w-full" :disabled="planBusy" @click="downloadPlan">{{ t("plan.download") }}</button>
          </div>
          <p class="text-xs text-slate-500" aria-live="polite">{{ planBusy ? t("plan.generating") : t("plan.printHint") }}</p>
          <router-link to="/settings" class="block text-xs link-action">{{ t("plan.workshopLink") }}</router-link>
        </div>
        <div class="flex-1 bg-slate-100 p-4 overflow-auto min-h-[320px] flex items-start justify-center">
          <p v-if="planError" class="text-sm text-red-600">{{ planError }}</p>
          <img
            v-else-if="planUrl"
            :src="planUrl"
            :alt="t('plan.previewAlt')"
            class="bg-paper shadow"
            :class="planZoom ? 'max-w-none w-[220%] cursor-zoom-out' : 'max-w-full cursor-zoom-in'"
            :title="t(planZoom ? 'plan.zoomOut' : 'plan.zoomIn')"
            @click="planZoom = !planZoom"
          />
        </div>
      </div>
    </div>
  </div>
</template>
