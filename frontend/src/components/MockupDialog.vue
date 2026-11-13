<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import Mockup3DView, { type PreviewMesh } from "@/components/Mockup3DView.vue";
import { saveBlob } from "@/composables/useApi";
import { fromDisplay, formatLengthWithUnit, toDisplay, type LengthUnit } from "@/editor/units";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

/** 3D mock-up of the assembled knife: a role and a thickness per part, a 3D view, and the
 * files for a 3D printer or a CNC router. Saves the design first (the server reads it). */
const props = defineProps<{ designId: number; designName: string; unit: LengthUnit }>();
const emit = defineEmits<{ (e: "close"): void }>();

const { t } = useI18n();
const store = useAppStore();

type Role = "blade" | "guard" | "bolster" | "spacer" | "liners" | "scales" | "liner_left" | "liner_right" | "scale_left" | "scale_right" | "";
const ROLES: Exclude<Role, "">[] = ["blade", "guard", "bolster", "spacer", "liners", "scales", "liner_left", "liner_right", "scale_left", "scale_right"];

interface Row { object_id: string; name: string; width_mm: number; height_mm: number; role: Role; thickness: number }
const rows = ref<Row[]>([]);
const opts = reactive({ output: "3mf" as "3mf" | "stl" | "cnc", layout: "flat" as "flat" | "assembled", clearance: 0.2, tool: 3 });
const meshes = ref<PreviewMesh[]>([]);
const issues = ref<{ part: string; kind: "corner" | "hole_too_small" | "hole_corner"; x: number; y: number; size_mm: number }[]>([]);
const stack = ref(0);
const explode = ref(1);
const error = ref("");
const busy = ref(false);
const loading = ref(true);

const D = (mm: number) => Math.round(toDisplay(mm, props.unit) * 10000) / 10000;
const L = (v: number) => fromDisplay(Number(v) || 0, props.unit);
const fmt = (mm: number) => formatLengthWithUnit(mm, props.unit);
const u = computed(() => (props.unit === "in" ? "in" : "mm"));

onMounted(async () => {
  try {
    const parts = await store.mockupParts(props.designId);
    rows.value = parts.map((p) => ({ ...p, role: (p.role ?? "") as Role, thickness: D(p.thickness_mm) }));
    clearanceDisplay.value = D(opts.clearance);
    toolDisplay.value = D(opts.tool);
    await refresh();
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    loading.value = false;
  }
});

const clearanceDisplay = ref(0.2);
const toolDisplay = ref(3);

function payload() {
  return {
    parts: rows.value.filter((r) => r.role).map((r) => ({ object_id: r.object_id, role: r.role, thickness_mm: L(r.thickness) })),
    pin_clearance_mm: L(clearanceDisplay.value),
    tool_diameter_mm: L(toolDisplay.value),
    output: opts.output,
    layout: opts.layout,
  };
}

let timer: ReturnType<typeof setTimeout> | null = null;
async function refresh() {
  const body = payload();
  if (!body.parts.length) {
    meshes.value = [];
    issues.value = [];
    stack.value = 0;
    return;
  }
  try {
    const r = await store.mockupPreview(props.designId, body);
    meshes.value = r.meshes;
    issues.value = r.issues;
    stack.value = r.stack_mm;
    error.value = "";
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}
watch([rows, () => opts.output, clearanceDisplay, toolDisplay], () => {
  if (timer) clearTimeout(timer);
  timer = setTimeout(refresh, 300);
}, { deep: true });

async function download() {
  busy.value = true;
  error.value = "";
  try {
    const blob = await store.mockupFile(props.designId, payload());
    const stem = props.designName.replace(/[^\w.-]+/g, "_");
    saveBlob(blob, opts.output === "3mf" ? `${stem}_maquette.3mf` : opts.output === "stl" ? `${stem}_maquette_stl.zip` : `${stem}_usinage_cnc.zip`);
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

const pins = computed(() => meshes.value.filter((m) => m.role === "pin").length);
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" role="dialog" aria-modal="true" aria-labelledby="mockup-title" @keydown.esc="emit('close')">
    <div class="bg-paper rounded-xl shadow-xl w-full max-w-6xl max-h-[92vh] overflow-y-auto p-5 text-sm">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 id="mockup-title" class="sheet-title">{{ t("mockup.title") }}</h2>
          <p class="text-slate-600 mt-1 max-w-prose">{{ t("mockup.lead") }}</p>
        </div>
        <button class="btn btn-outline btn-sm" @click="emit('close')">{{ t("common.close") }}</button>
      </div>

      <p v-if="loading" class="mt-4 text-slate-500">{{ t("common.loading") }}</p>
      <div v-else class="mt-4 grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div class="space-y-4 min-w-0">
          <table class="w-full">
            <thead>
              <tr class="text-left text-xs text-slate-500">
                <th class="font-medium pb-1">{{ t("mockup.part") }}</th>
                <th class="font-medium pb-1">{{ t("mockup.role") }}</th>
                <th class="font-medium pb-1 text-right">{{ t("mockup.thickness", { u }) }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.object_id" class="border-t border-slate-100">
                <td class="py-1.5 pr-2">
                  <span class="block font-medium">{{ r.name }}</span>
                  <span class="block text-xs text-slate-500">{{ fmt(r.width_mm) }} × {{ fmt(r.height_mm) }}</span>
                </td>
                <td class="py-1.5 pr-2">
                  <select v-model="r.role" class="input-sm w-full" :aria-label="t('mockup.role')">
                    <option value="">{{ t("mockup.ignored") }}</option>
                    <option v-for="role in ROLES" :key="role" :value="role">{{ t(`mockup.roles.${role}`) }}</option>
                  </select>
                </td>
                <td class="py-1.5 text-right">
                  <input v-model.number="r.thickness" type="number" min="0.1" step="any" :disabled="!r.role" class="input-sm w-20 text-right" :aria-label="t('mockup.thickness', { u })" />
                </td>
              </tr>
            </tbody>
          </table>
          <p class="text-xs text-slate-500">{{ t("mockup.stackHint") }}</p>

          <div class="flex flex-wrap gap-1" role="tablist">
            <button v-for="o in (['3mf', 'stl', 'cnc'] as const)" :key="o" type="button" role="tab" :aria-selected="opts.output === o"
                    class="px-3 py-1.5 rounded-lg border text-sm"
                    :class="opts.output === o ? 'bg-slate-800 text-paper border-slate-800' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
                    @click="opts.output = o">{{ t(`mockup.outputs.${o}`) }}</button>
          </div>

          <div v-if="opts.output !== 'cnc'" class="grid gap-3 sm:grid-cols-2">
            <label class="block">
              <span class="field-label">{{ t("mockup.clearance", { u }) }}</span>
              <input v-model.number="clearanceDisplay" type="number" min="0" step="any" class="input w-full" />
              <span class="block mt-1 text-xs text-slate-500">{{ t("mockup.clearanceHint") }}</span>
            </label>
            <label v-if="opts.output === '3mf'" class="block">
              <span class="field-label">{{ t("mockup.layout") }}</span>
              <select v-model="opts.layout" class="input w-full">
                <option value="flat">{{ t("mockup.layouts.flat") }}</option>
                <option value="assembled">{{ t("mockup.layouts.assembled") }}</option>
              </select>
            </label>
          </div>
          <div v-else class="space-y-2">
            <label class="block">
              <span class="field-label">{{ t("mockup.tool", { u }) }}</span>
              <input v-model.number="toolDisplay" type="number" min="0.1" step="any" class="input w-32" />
            </label>
            <p v-if="!issues.length" class="text-emerald-700">{{ t("mockup.toolOk") }}</p>
            <ul v-else class="space-y-1 text-amber-800">
              <li v-for="(i, n) in issues" :key="n">{{ t(`mockup.issue.${i.kind}`, { part: i.part, size: fmt(i.size_mm), x: fmt(i.x), y: fmt(i.y) }) }}</li>
            </ul>
            <p class="text-xs text-slate-500">{{ t("mockup.cncHint") }}</p>
          </div>

          <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
          <div class="flex flex-wrap items-center gap-3">
            <button class="btn btn-primary" :disabled="busy || !meshes.length" @click="download">{{ t(`mockup.download.${opts.output}`) }}</button>
            <span v-if="meshes.length" class="text-xs text-slate-500">{{ t("mockup.summary", { n: meshes.length - pins, pins, stack: fmt(stack) }) }}</span>
          </div>
          <p class="text-xs text-slate-500">{{ t("mockup.limits") }}</p>
        </div>

        <div class="min-w-0 flex flex-col gap-2">
          <div class="h-[420px]"><Mockup3DView :meshes="meshes" :explode="explode" /></div>
          <label class="flex items-center gap-3 text-xs text-slate-600">
            {{ t("mockup.explode") }}
            <input v-model.number="explode" type="range" min="1" max="4" step="0.05" class="flex-1" />
          </label>
          <p class="text-xs text-slate-500">{{ t("mockup.viewHint") }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
