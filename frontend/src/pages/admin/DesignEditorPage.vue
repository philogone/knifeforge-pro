<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, useRoute } from "vue-router";

import { ApiError, saveBlob } from "@/composables/useApi";
import { useSnapshotDirty } from "@/composables/useSnapshotDirty";
import { initialPlacement, loadImageFile, mmPerPixel, type BackgroundState, type Straighten } from "@/editor/background";
import { ROLE_STYLE } from "@/editor/constants";
import { EditorEngine, formatMm } from "@/editor/engine";
import type { AlignKind, BooleanOp, Measurement, SnapKind, SnapOptions } from "@/editor/engine";
import type { DocLayer, Guide, LayerRole, SelectionInfo, ToolName } from "@/editor/types";
import { RULER_SIZE, drawGrid, drawRulers, screenToWorld } from "@/editor/view";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { Design, DesignKind } from "@/types";

const { t } = useI18n();
const store = useAppStore();
const route = useRoute();

const kinds: DesignKind[] = ["blade", "handle_scale", "guard", "bolster", "sheath", "template", "other"];
const roles: LayerRole[] = ["cut", "hole", "engrave", "construction", "dimension"];
const tools: { name: ToolName; icon: string }[] = [
  { name: "select", icon: "↖" },
  { name: "node", icon: "◇" },
  { name: "pen", icon: "✒" },
  { name: "rect", icon: "▭" },
  { name: "ellipse", icon: "◯" },
  { name: "line", icon: "∕" },
  { name: "polygon", icon: "⬡" },
  { name: "dimension", icon: "↔" },
  { name: "measure", icon: "📏" },
  { name: "pan", icon: "✋" },
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
const calib = reactive({ open: false, a: [0, 0] as [number, number], b: [0, 0] as [number, number], real: "" as number | "", straighten: "horizontal" as Straighten, origin: false });
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
  drawRulers(ctx, e.viewTransform, e.cursor, e.guides, e.previewGuide);
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
      zoomPct.value = Math.round((e.zoom / (96 / 25.4)) * 100);
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
    e.on("background", () => (bg.value = e.background)),
    e.on("calibrate", (a, b) => {
      calib.a = a;
      calib.b = b;
      // left empty on purpose: pre-filling the measured value would let "Apply" mark an
      // uncalibrated image as calibrated
      calib.real = "";
      calib.open = true;
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
    loadError.value = err instanceof ApiError ? err.message : "Failed";
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
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("beforeunload", onBeforeUnload);
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
    setStatus(t("editor.saveFailed", { error: err instanceof ApiError ? err.message : "?" }), true);
    return false;
  } finally {
    saving.value = false;
  }
}

async function exportFile(kind: "export.svg" | "export.dxf") {
  if (unsaved.value && !(await save())) return;
  try {
    const blob = await store.downloadDesignFile(designId.value, kind);
    saveBlob(blob, `${meta.name.replace(/[^\w.-]+/g, "_")}.${kind.split(".")[1]}`);
  } catch (err) {
    setStatus(t("designs.exportFailed", { error: err instanceof ApiError ? err.message : "?" }), true);
  }
}

// ------------------------------------------------------------------ import
const fileInput = ref<HTMLInputElement | null>(null);
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
  if (tool.value === "calibrate") engine.value?.setTool("select");
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
function isTyping(ev: KeyboardEvent) {
  const el = ev.target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

const TOOL_KEYS: Record<string, ToolName> = { v: "select", n: "node", p: "pen", r: "rect", e: "ellipse", l: "line", g: "polygon", d: "dimension", m: "measure", h: "pan" };

function onKeyDown(ev: KeyboardEvent) {
  const e = engine.value;
  if (!e || isTyping(ev) || planOpen.value || calib.open) return;
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
    setStatus(t("editor.offsetFailed", { error: err instanceof ApiError ? err.message : "?" }), true);
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
const planBusy = ref(false);
const planError = ref("");
const planUrl = ref("");
const planForm = reactive({ paper: "A4", scale: "", customer: "", order_ref: "", title: "", notes: "" });

async function openPlan() {
  if (unsaved.value && !(await save())) return;
  planForm.title ||= meta.name;
  planOpen.value = true;
  await refreshPlan();
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
    planError.value = t("plan.failed", { error: err instanceof ApiError ? err.message : "?" });
  } finally {
    planBusy.value = false;
  }
}

async function downloadPlan() {
  try {
    const blob = await store.designPlan(designId.value, planParams(), true);
    saveBlob(blob, `plan_${meta.name.replace(/[^\w.-]+/g, "_")}.svg`);
  } catch (err) {
    planError.value = t("plan.failed", { error: err instanceof ApiError ? err.message : "?" });
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
  <div class="h-[calc(100vh-57px)] flex flex-col bg-slate-100">
    <p v-if="loadError" class="p-6 text-red-600 text-sm">{{ loadError }}</p>

    <template v-else>
      <!-- top bar -->
      <div class="bg-white border-b border-slate-200 px-3 py-2 flex items-center gap-2 flex-wrap text-sm">
        <router-link to="/designs" class="text-slate-500 hover:text-slate-900">← {{ t("editor.back") }}</router-link>
        <input
          v-model="meta.name"
          class="font-semibold text-slate-900 border border-transparent hover:border-slate-300 focus:border-indigo-400 rounded px-2 py-1 w-56"
        />
        <span v-if="unsaved" class="text-amber-600 text-xs">● {{ t("editor.unsaved") }}</span>
        <span v-else class="text-emerald-600 text-xs">✓ {{ t("editor.saved") }}</span>
        <div class="flex-1"></div>
        <button class="px-2 py-1 rounded border border-slate-300 disabled:opacity-40" :disabled="!canUndo" :title="t('editor.undo')" @click="engine?.undo()">↶</button>
        <button class="px-2 py-1 rounded border border-slate-300 disabled:opacity-40" :disabled="!canRedo" :title="t('editor.redo')" @click="engine?.redo()">↷</button>
        <button class="px-2 py-1 rounded border border-slate-300" :title="t('editor.fit')" @click="engine?.zoomToFit()">⤢</button>
        <button class="px-2 py-1 rounded border border-slate-300" :title="t('editor.zoomActual')" @click="engine?.zoomActual()">1:1</button>
        <button class="px-2 py-1 rounded border border-slate-300" @click="fileInput?.click()">{{ t("editor.importSvg") }}</button>
        <input ref="fileInput" type="file" accept=".svg,image/svg+xml" class="hidden" @change="onImport" />
        <button class="px-2 py-1 rounded border border-slate-300" @click="exportFile('export.svg')">{{ t("editor.exportSvg") }}</button>
        <button class="px-2 py-1 rounded border border-slate-300" @click="exportFile('export.dxf')">{{ t("editor.exportDxf") }}</button>
        <button class="px-2 py-1 rounded border border-slate-300" @click="openPlan">{{ t("editor.plan") }}</button>
        <button
          class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-medium rounded-lg px-4 py-1.5"
          :disabled="saving || !unsaved"
          @click="save"
        >
          {{ saving ? t("editor.saving") : t("editor.save") }}
        </button>
      </div>

      <!-- options bar -->
      <div class="bg-white border-b border-slate-200 px-3 py-1.5 flex items-center gap-4 flex-wrap text-xs text-slate-600">
        <label class="flex items-center gap-1"><input v-model="snapOpts.grid" type="checkbox" /> {{ t("editor.snapGrid") }}</label>
        <label class="flex items-center gap-1"><input v-model="snapOpts.nodes" type="checkbox" /> {{ t("editor.snapNodes") }}</label>
        <label class="flex items-center gap-1">
          {{ t("editor.gridSize") }}
          <input v-model.number="opts.gridSize" type="number" min="0.01" max="1000" step="any" list="grid-presets" class="w-16 border border-slate-300 rounded px-1 py-0.5" />
          <datalist id="grid-presets"><option v-for="g in [0.1, 0.25, 0.5, 1, 2, 5, 10, 25]" :key="g" :value="g"></option></datalist>
        </label>
        <label class="flex items-center gap-1"><input v-model="opts.showGrid" type="checkbox" /> {{ t("editor.showGrid") }}</label>
        <details class="relative">
          <summary class="cursor-pointer select-none text-slate-700">🧲 {{ t("editor.snapMenu") }}</summary>
          <div class="absolute z-20 mt-1 w-72 bg-white border border-slate-200 rounded-lg shadow-lg p-3 space-y-1">
            <label v-for="k in snapKinds" :key="k" class="flex items-center gap-2"><input v-model="snapOpts[k]" type="checkbox" /> {{ t(`snap.opt.${k}`) }}</label>
            <label class="flex items-center gap-2 pt-1">{{ t("editor.snapRadius") }}
              <input v-model.number="opts.snapRadius" type="number" min="2" max="40" class="w-14 border border-slate-300 rounded px-1 py-0.5" />
            </label>
            <p class="text-[11px] text-slate-400 pt-1">{{ t("snap.help") }}</p>
          </div>
        </details>
        <label v-if="tool === 'rect'" class="flex items-center gap-1">
          {{ t("editor.cornerRadius") }}
          <input v-model.number="opts.cornerRadius" type="number" min="0" step="0.5" class="w-16 border border-slate-300 rounded px-1 py-0.5" />
        </label>
        <label v-if="tool === 'polygon'" class="flex items-center gap-1">
          {{ t("editor.polygonSides") }}
          <input v-model.number="opts.polygonSides" type="number" min="3" max="64" class="w-16 border border-slate-300 rounded px-1 py-0.5" />
        </label>
        <span v-if="activeLayerBlocked" class="text-amber-600">⚠ {{ t("editor.layerLockedHint") }}</span>
      </div>

      <div class="flex-1 flex min-h-0">
        <!-- toolbar -->
        <div class="w-12 bg-white border-r border-slate-200 flex flex-col items-center py-2 gap-1">
          <button
            v-for="tl in tools"
            :key="tl.name"
            class="w-9 h-9 rounded-lg text-lg flex items-center justify-center"
            :class="tool === tl.name ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'"
            :title="toolLabel(tl.name)"
            @click="engine?.setTool(tl.name)"
          >
            {{ tl.icon }}
          </button>
        </div>

        <!-- canvas stack -->
        <div ref="stage" class="flex-1 relative overflow-hidden min-w-0">
          <canvas ref="gridCanvas" class="absolute inset-0 pointer-events-none"></canvas>
          <canvas ref="paperCanvas" class="absolute inset-0" style="touch-action: none"></canvas>
          <canvas ref="rulerCanvas" class="absolute inset-0 pointer-events-none"></canvas>
          <!-- drag a guide out of a ruler -->
          <div class="absolute top-0 right-0 cursor-row-resize" :style="{ left: `${RULER_SIZE}px`, height: `${RULER_SIZE}px` }" @pointerdown="startGuide('y', $event)"></div>
          <div class="absolute left-0 bottom-0 cursor-col-resize" :style="{ top: `${RULER_SIZE}px`, width: `${RULER_SIZE}px` }" @pointerdown="startGuide('x', $event)"></div>
          <p v-if="!design && !loadError" class="absolute inset-0 flex items-center justify-center text-sm text-slate-500">{{ t("editor.loading") }}</p>
        </div>

        <!-- right panel -->
        <aside class="w-80 bg-white border-l border-slate-200 flex flex-col min-h-0">
          <div class="flex border-b border-slate-200 text-sm">
            <button
              v-for="id in ['object', 'layers', 'background', 'document'] as const"
              :key="id"
              class="flex-1 py-2"
              :class="tab === id ? 'border-b-2 border-indigo-600 text-indigo-600 font-medium' : 'text-slate-500'"
              @click="tab = id"
            >
              {{ t(`editor.tab.${id}`) }}
            </button>
          </div>

          <div class="flex-1 overflow-y-auto p-3 space-y-4 text-sm">
            <!-- OBJECT TAB -->
            <template v-if="tab === 'object'">
              <div v-if="tool === 'measure'" class="bg-sky-50 border border-sky-200 rounded-lg p-2 text-xs text-slate-700 space-y-0.5">
                <p class="font-medium text-sky-800">{{ t("measure.title") }}</p>
                <template v-if="measurement">
                  <p>{{ t("measure.distance") }} : <b class="font-mono">{{ formatMm(measurement.distance) }} mm</b></p>
                  <p class="font-mono">ΔX {{ formatMm(measurement.dx) }} · ΔY {{ formatMm(measurement.dy) }} mm</p>
                  <p>{{ t("measure.angle") }} : <span class="font-mono">{{ measurement.angle }}°</span></p>
                  <button class="mt-1 w-full px-2 py-1 rounded border border-sky-300 bg-white" @click="engine?.measurementToDimension()">{{ t("measure.toDimension") }}</button>
                </template>
                <p v-else class="text-slate-500">{{ t("measure.empty") }}</p>
              </div>
              <p v-if="!sel.count" class="text-slate-500 text-xs">{{ t("editor.nothingSelected") }}</p>

              <template v-else>
                <p class="text-xs text-slate-500">{{ t("editor.selectedCount", { n: sel.count }) }}</p>

                <div v-if="sel.count === 1">
                  <label class="block text-xs text-slate-500 mb-1">{{ t("editor.objectName") }}</label>
                  <input :value="sel.name ?? ''" class="w-full border border-slate-300 rounded px-2 py-1" @change="setName" />
                </div>

                <div>
                  <label class="block text-xs text-slate-500 mb-1">{{ t("editor.layer") }}</label>
                  <select :value="sel.layerId ?? ''" class="w-full border border-slate-300 rounded px-2 py-1" @change="moveToLayer">
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
                    <label class="text-xs text-slate-500">X <input v-model.number="bounds.x" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBound('x')" /></label>
                    <label class="text-xs text-slate-500">Y <input v-model.number="bounds.y" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBound('y')" /></label>
                    <label class="text-xs text-slate-500">L <input v-model.number="bounds.w" type="number" step="any" min="0" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBound('w')" /></label>
                    <label class="text-xs text-slate-500">H <input v-model.number="bounds.h" type="number" step="any" min="0" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBound('h')" /></label>
                  </div>
                </div>

                <div class="flex items-end gap-2">
                  <label class="text-xs text-slate-500 flex-1">{{ t("editor.rotateBy") }}
                    <input v-model.number="rotateBy" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @keydown.enter="applyRotation" @change="applyRotation" />
                  </label>
                  <button class="px-2 py-1 rounded border border-slate-300" @click="engine?.rotateSelection(90)">{{ t("editor.rotate90") }}</button>
                </div>

                <div class="grid grid-cols-2 gap-2">
                  <button class="px-2 py-1 rounded border border-slate-300" @click="engine?.flipSelection('h')">{{ t("editor.flipH") }}</button>
                  <button class="px-2 py-1 rounded border border-slate-300" @click="engine?.flipSelection('v')">{{ t("editor.flipV") }}</button>
                  <button class="px-2 py-1 rounded border border-slate-300" @click="engine?.mirrorCopy('h')">{{ t("editor.mirrorH") }}</button>
                  <button class="px-2 py-1 rounded border border-slate-300" @click="engine?.mirrorCopy('v')">{{ t("editor.mirrorV") }}</button>
                  <button class="px-2 py-1 rounded border border-slate-300" @click="engine?.duplicateSelection()">{{ t("editor.duplicate") }}</button>
                  <button class="px-2 py-1 rounded border border-red-300 text-red-600" @click="engine?.deleteSelection()">{{ t("editor.delete") }}</button>
                </div>

                <div v-if="sel.count > 1">
                  <p class="text-xs text-slate-500 mb-1">{{ t("editor.align") }}</p>
                  <div class="grid grid-cols-3 gap-1">
                    <button v-for="k in alignKinds" :key="k" class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.align(k)">{{ t(`editor.align.${k}`) }}</button>
                  </div>
                  <div v-if="sel.count > 2" class="grid grid-cols-2 gap-1 mt-1">
                    <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.distribute('h')">{{ t("editor.distributeH") }}</button>
                    <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.distribute('v')">{{ t("editor.distributeV") }}</button>
                  </div>
                </div>

                <div>
                  <p class="text-xs text-slate-500 mb-1">{{ t("editor.boolean") }}</p>
                  <div class="grid grid-cols-2 gap-1">
                    <button v-for="op in booleanOps" :key="op" class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.booleanOp(op)">{{ t(`editor.boolean.${op}`) }}</button>
                    <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.combine()">{{ t("editor.combine") }}</button>
                    <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.breakApart()">{{ t("editor.breakApart") }}</button>
                  </div>
                  <p class="text-[11px] text-slate-400 mt-1">{{ t("editor.booleanHelp") }}</p>
                </div>

                <div v-if="sel.path" class="bg-slate-50 rounded-lg p-2 text-xs text-slate-600 space-y-0.5">
                  <p class="font-medium text-slate-700">{{ t("editor.shapeInfo") }}</p>
                  <p>{{ sel.path.closed ? t("editor.closedShape") : t("editor.openPath") }}</p>
                  <p>{{ t("editor.nodeCount") }} : {{ sel.path.nodeCount }}</p>
                  <p v-if="sel.path.closed">{{ t("editor.area") }} : {{ formatMm(sel.path.area) }} mm² ({{ formatMm(sel.path.area / 100) }} cm²)</p>
                  <p>{{ t("editor.perimeter") }} : {{ formatMm(sel.path.perimeter) }} mm</p>
                </div>

                <div v-if="sel.path && sel.path.closed" class="space-y-2">
                  <p class="text-xs font-medium text-slate-700">{{ t("editor.offsetTitle") }}</p>
                  <label class="block text-xs text-slate-500">{{ t("editor.offsetDistance") }}
                    <input v-model.number="offsetForm.distance" type="number" step="0.1" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" />
                  </label>
                  <label class="block text-xs text-slate-500">{{ t("editor.offsetJoin") }}
                    <select v-model="offsetForm.join" class="w-full border border-slate-300 rounded px-2 py-1 text-sm">
                      <option value="round">{{ t("editor.offsetJoin.round") }}</option>
                      <option value="mitre">{{ t("editor.offsetJoin.mitre") }}</option>
                      <option value="bevel">{{ t("editor.offsetJoin.bevel") }}</option>
                    </select>
                  </label>
                  <label class="text-xs text-slate-500 flex items-center gap-1"><input v-model="offsetForm.keep" type="checkbox" /> {{ t("editor.offsetKeep") }}</label>
                  <button class="w-full px-2 py-1 rounded border border-indigo-300 text-indigo-700 bg-indigo-50" @click="applyOffset">{{ t("editor.offsetApply") }}</button>
                </div>

                <div v-if="sel.dimension" class="space-y-2">
                  <p class="text-xs font-medium text-slate-700">{{ t("editor.dimTitle") }}</p>
                  <p class="text-xs text-slate-500">{{ t("editor.dimLength") }} : {{ formatMm(sel.dimension.length) }} mm</p>
                  <label class="block text-xs text-slate-500">{{ t("editor.dimOffset") }}
                    <input v-model.number="dimForm.offset" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="applyDimension" />
                  </label>
                  <label class="block text-xs text-slate-500">{{ t("editor.dimLabel") }}
                    <input v-model="dimForm.label" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="applyDimension" />
                  </label>
                </div>
              </template>

              <div v-if="tool === 'node' || sel.selectedNodes" class="space-y-2 border-t border-slate-100 pt-3">
                <p class="text-xs font-medium text-slate-700">{{ t("editor.nodesTitle") }}</p>
                <p class="text-xs text-slate-500">{{ t("editor.nodesSelected", { n: sel.selectedNodes }) }}</p>
                <div v-if="sel.singleNode" class="grid grid-cols-2 gap-2">
                  <label class="text-xs text-slate-500">{{ t("editor.nodeX") }} <input v-model.number="nodeXY.x" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="applyNodeXY" /></label>
                  <label class="text-xs text-slate-500">{{ t("editor.nodeY") }} <input v-model.number="nodeXY.y" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="applyNodeXY" /></label>
                </div>
                <div class="grid grid-cols-2 gap-1">
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.deleteSelectedNodes()">{{ t("editor.nodeDelete") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.insertNodes()">{{ t("editor.nodeInsert") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.setNodeType('smooth')">{{ t("editor.nodeSmooth") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.setNodeType('corner')">{{ t("editor.nodeCorner") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.toggleClosed()">{{ t("editor.nodeToggleClosed") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.reversePaths()">{{ t("editor.nodeReverse") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.simplifyPaths()">{{ t("editor.nodeSimplify") }}</button>
                  <button class="px-1 py-1 rounded border border-slate-300 text-xs" @click="engine?.flattenPaths()">{{ t("editor.nodeFlatten") }}</button>
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
                  :class="l.id === activeLayerId ? 'border-indigo-400 bg-indigo-50/40' : 'border-slate-200'"
                >
                  <div class="flex items-center gap-1">
                    <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ background: roleColor(l.role) }"></span>
                    <input :value="l.name" class="flex-1 min-w-0 border border-transparent hover:border-slate-300 rounded px-1 py-0.5" @change="patchLayer(l, { name: ($event.target as HTMLInputElement).value })" />
                    <button :title="t('editor.layerVisible')" class="px-1" :class="l.visible ? 'text-slate-700' : 'text-slate-300'" @click="patchLayer(l, { visible: !l.visible })">👁</button>
                    <button :title="t('editor.layerLocked')" class="px-1" :class="l.locked ? 'text-amber-600' : 'text-slate-300'" @click="patchLayer(l, { locked: !l.locked })">🔒</button>
                  </div>
                  <div class="flex items-center gap-1">
                    <select :value="l.role" class="flex-1 min-w-0 border border-slate-300 rounded px-1 py-0.5 text-xs" @change="patchLayer(l, { role: ($event.target as HTMLSelectElement).value as LayerRole })">
                      <option v-for="r in roles" :key="r" :value="r">{{ t(`editor.role.${r}`) }}</option>
                    </select>
                    <button class="px-1 text-xs" :title="t('editor.layerUp')" :disabled="i === 0" @click="moveLayer(l, 1)">▲</button>
                    <button class="px-1 text-xs" :title="t('editor.layerDown')" :disabled="i === layers.length - 1" @click="moveLayer(l, -1)">▼</button>
                    <button class="px-1 text-xs text-red-600" :title="t('editor.layerDelete')" :disabled="layers.length <= 1" @click="removeLayer(l)">✕</button>
                  </div>
                  <button class="text-xs" :class="l.id === activeLayerId ? 'text-indigo-700 font-medium' : 'text-slate-500'" @click="setActive(l)">
                    {{ l.id === activeLayerId ? "● " : "○ " }}{{ t("editor.layerActive") }}
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
                <button class="w-full px-2 py-1.5 rounded-lg bg-indigo-600 text-white" @click="pickBackground">{{ t("bg.import") }}</button>
              </template>
              <template v-else>
                <div class="flex items-center gap-3 text-xs">
                  <label class="flex items-center gap-1"><input type="checkbox" :checked="bg.visible" @change="engine?.updateBackground({ visible: ($event.target as HTMLInputElement).checked })" /> {{ t("bg.visible") }}</label>
                  <label class="flex items-center gap-1 flex-1">{{ t("bg.opacity") }}
                    <input type="range" min="5" max="100" :value="Math.round(bg.opacity * 100)" class="flex-1" @input="engine?.updateBackground({ opacity: Number(($event.target as HTMLInputElement).value) / 100 })" />
                  </label>
                </div>
                <button class="w-full px-2 py-1.5 rounded-lg border border-rose-300 text-rose-700 bg-rose-50" @click="engine?.setTool('calibrate')">📐 {{ t("bg.calibrate") }}</button>
                <div class="rounded-lg p-2 text-xs space-y-1" :class="bg.calibrated ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'">
                  <p>{{ bg.calibrated ? `✓ ${t("bg.calibrated")}` : `⚠ ${t("bg.notCalibrated")}` }}</p>
                  <p v-if="bg.calibrated && bgResolution">{{ t("bg.resolution", { mm: formatMm(bgResolution) }) }}</p>
                  <p v-if="bg.calibrated && bgResolution && bgResolution > 0.1" class="text-amber-700">{{ t("bg.resolutionWarn") }}</p>
                </div>
                <div>
                  <p class="text-xs text-slate-500 mb-1">{{ t("bg.placement") }}</p>
                  <div class="grid grid-cols-2 gap-2">
                    <label class="text-xs text-slate-500">{{ t("bg.centerX") }} <input :value="bg.cx" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBgField('cx', $event)" /></label>
                    <label class="text-xs text-slate-500">{{ t("bg.centerY") }} <input :value="bg.cy" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBgField('cy', $event)" /></label>
                    <label class="text-xs text-slate-500">{{ t("bg.width") }} <input :value="bg.width_mm" type="number" step="any" min="0" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBgField('width_mm', $event)" /></label>
                    <label class="text-xs text-slate-500">{{ t("bg.height") }} <input :value="bg.height_mm" type="number" step="any" min="0" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBgField('height_mm', $event)" /></label>
                    <label class="text-xs text-slate-500 col-span-2">{{ t("bg.rotation") }} <input :value="bg.rotation_deg" type="number" step="any" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" @change="setBgField('rotation_deg', $event)" /></label>
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
                <label class="block text-xs text-slate-500 mb-1">{{ t("editor.docKind") }}</label>
                <select v-model="meta.kind" class="w-full border border-slate-300 rounded px-2 py-1">
                  <option v-for="k in kinds" :key="k" :value="k">{{ t(`designs.kind.${k}`) }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">{{ t("designs.knifeModel") }}</label>
                <select v-model.number="meta.knife_model_id" class="w-full border border-slate-300 rounded px-2 py-1">
                  <option :value="0">{{ t("designs.none") }}</option>
                  <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">{{ t("designs.material") }}</label>
                <select v-model.number="meta.material_id" class="w-full border border-slate-300 rounded px-2 py-1">
                  <option :value="0">{{ t("designs.none") }}</option>
                  <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">{{ t("editor.docNotes") }}</label>
                <textarea v-model="meta.notes" rows="3" class="w-full border border-slate-300 rounded px-2 py-1"></textarea>
              </div>
              <div v-if="design" class="bg-slate-50 rounded-lg p-2 text-xs text-slate-600 space-y-0.5">
                <p class="font-medium text-slate-700">{{ t("editor.docMetrics") }}</p>
                <p>{{ design.width_mm.toFixed(1) }} × {{ design.height_mm.toFixed(1) }} mm</p>
                <p>{{ t("editor.area") }} : {{ (design.area_mm2 / 100).toFixed(2) }} cm²</p>
                <p>{{ t("editor.perimeter") }} : {{ design.perimeter_mm.toFixed(1) }} mm</p>
                <p>{{ t("editor.docParts") }} : {{ design.part_count }}</p>
                <p class="text-slate-400">{{ t("editor.docMetricsHint") }}</p>
              </div>
              <div class="space-y-2 border-t border-slate-100 pt-3">
                <p class="text-xs font-medium text-slate-700">{{ t("guides.title") }}</p>
                <p class="text-[11px] text-slate-400">{{ t("guides.help") }}</p>
                <p v-if="!guides.length" class="text-xs text-slate-500">{{ t("guides.none") }}</p>
                <div v-for="(g, i) in guides" :key="i" class="flex items-center gap-1 text-xs">
                  <span class="w-28 text-slate-500">{{ g.axis === "x" ? t("guides.vertical") : t("guides.horizontal") }}</span>
                  <input :value="g.pos" type="number" step="any" class="flex-1 min-w-0 border border-slate-300 rounded px-1 py-0.5" @change="setGuidePos(i, $event)" />
                  <button class="px-1 text-red-600" @click="engine?.removeGuide(i)">✕</button>
                </div>
                <div class="grid grid-cols-2 gap-1 text-xs">
                  <input v-model.number="guideForm.x" type="number" step="any" class="border border-slate-300 rounded px-1 py-0.5" />
                  <button class="px-1 py-0.5 rounded border border-slate-300" @click="addGuideAt('x')">{{ t("guides.addV") }}</button>
                  <input v-model.number="guideForm.y" type="number" step="any" class="border border-slate-300 rounded px-1 py-0.5" />
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
      <div class="bg-white border-t border-slate-200 px-3 py-1 text-xs text-slate-500 flex items-center gap-4">
        <span class="flex-1 truncate">{{ hintText }}</span>
        <span v-if="valueHint" class="font-mono text-indigo-600">{{ valueHint }}</span>
        <span v-if="status" :class="statusIsError ? 'text-red-600' : 'text-emerald-600'">{{ status }}</span>
        <span>{{ t("editor.cursor") }} : {{ cursorText }}</span>
        <span>{{ t("editor.zoom") }} : {{ zoomPct }} %</span>
      </div>
    </template>

    <!-- calibration dialog -->
    <div v-if="calib.open" class="fixed inset-0 bg-slate-900/40 z-50 flex items-center justify-center p-4" @click.self="cancelCalibration">
      <form class="bg-white rounded-xl shadow-xl w-full max-w-sm p-4 space-y-3 text-sm" @submit.prevent="applyCalibration">
        <h2 class="font-semibold text-slate-900">{{ t("calib.title") }}</h2>
        <p class="text-xs text-slate-500">{{ t("calib.measured", { d: formatMm(Math.hypot(calib.b[0] - calib.a[0], calib.b[1] - calib.a[1])) }) }}</p>
        <label class="block text-xs text-slate-500">{{ t("calib.real") }}
          <input v-model.number="calib.real" type="number" min="0.01" step="any" required autofocus placeholder="ex. 100" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" />
        </label>
        <label class="block text-xs text-slate-500">{{ t("calib.straighten") }}
          <select v-model="calib.straighten" class="w-full border border-slate-300 rounded px-2 py-1 text-sm">
            <option v-for="o in ['none', 'horizontal', 'vertical']" :key="o" :value="o">{{ t(`calib.straighten.${o}`) }}</option>
          </select>
        </label>
        <label class="flex items-center gap-2 text-xs text-slate-600"><input v-model="calib.origin" type="checkbox" /> {{ t("calib.origin") }}</label>
        <div class="flex gap-2 justify-end">
          <button type="button" class="px-3 py-1.5 rounded border border-slate-300" @click="cancelCalibration">{{ t("common.cancel") }}</button>
          <button type="submit" class="px-3 py-1.5 rounded bg-indigo-600 text-white">{{ t("calib.apply") }}</button>
        </div>
      </form>
    </div>

    <!-- plan modal -->
    <div v-if="planOpen" class="fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4" @click.self="planOpen = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[92vh] flex flex-col md:flex-row overflow-hidden">
        <div class="md:w-72 p-4 space-y-3 overflow-y-auto border-b md:border-b-0 md:border-r border-slate-200 text-sm">
          <h2 class="font-semibold text-slate-900">{{ t("plan.title") }}</h2>
          <label class="block text-xs text-slate-500">{{ t("plan.paper") }}
            <select v-model="planForm.paper" class="w-full border border-slate-300 rounded px-2 py-1 text-sm">
              <option>A4</option>
              <option>A3</option>
            </select>
          </label>
          <label class="block text-xs text-slate-500">{{ t("plan.scale") }}
            <select v-model="planForm.scale" class="w-full border border-slate-300 rounded px-2 py-1 text-sm">
              <option value="">{{ t("plan.scaleAuto") }}</option>
              <option v-for="s in [1, 2, 0.5, 0.25, 0.2, 0.1]" :key="s" :value="String(s)">{{ s >= 1 ? `${s}:1` : `1:${Math.round(1 / s)}` }}</option>
            </select>
          </label>
          <label class="block text-xs text-slate-500">{{ t("plan.planTitle") }}<input v-model="planForm.title" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" /></label>
          <label class="block text-xs text-slate-500">{{ t("plan.customer") }}<input v-model="planForm.customer" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" /></label>
          <label class="block text-xs text-slate-500">{{ t("plan.orderRef") }}<input v-model="planForm.order_ref" class="w-full border border-slate-300 rounded px-2 py-1 text-sm" /></label>
          <label class="block text-xs text-slate-500">{{ t("plan.notes") }}<textarea v-model="planForm.notes" rows="2" class="w-full border border-slate-300 rounded px-2 py-1 text-sm"></textarea></label>
          <button class="w-full px-3 py-1.5 rounded-lg bg-indigo-600 text-white" :disabled="planBusy" @click="refreshPlan">{{ planBusy ? t("plan.generating") : "↻" }}</button>
          <div class="flex gap-2">
            <button class="flex-1 px-2 py-1.5 rounded border border-slate-300" @click="downloadPlan">{{ t("plan.download") }}</button>
            <button class="flex-1 px-2 py-1.5 rounded border border-slate-300" :disabled="!planUrl" @click="printPlan">{{ t("plan.print") }}</button>
          </div>
          <p class="text-[11px] text-slate-400">{{ t("plan.needSave") }}</p>
          <button class="w-full text-slate-500 text-sm" @click="planOpen = false">{{ t("common.close") }}</button>
        </div>
        <div class="flex-1 bg-slate-100 p-4 overflow-auto min-h-[320px] flex items-start justify-center">
          <p v-if="planError" class="text-sm text-red-600">{{ planError }}</p>
          <img v-else-if="planUrl" :src="planUrl" alt="plan" class="max-w-full bg-white shadow" />
        </div>
      </div>
    </div>
  </div>
</template>
