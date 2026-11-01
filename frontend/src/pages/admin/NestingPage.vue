<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import NestingSheetVisual from "@/components/NestingSheetVisual.vue";
import { ApiError, saveBlob } from "@/composables/useApi";
import { formatDecimal, useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { NestingCandidates, NestingRequest, NestingResult } from "@/types";

const { t, locale } = useI18n();
const store = useAppStore();

const materialId = ref(0);
const candidates = ref<NestingCandidates | null>(null);
const selectedOrders = ref<number[]>([]);
const extras = reactive<Record<number, number>>({});
const spacing = ref(2);
const margin = ref(3);
const rotationMode = ref<"all" | "flip" | "fixed">("all");
const result = ref<NestingResult | null>(null);
const activeSheet = ref(0);
const busy = ref(false);
const error = ref("");
// the request that produced `result`, so exports match exactly what is displayed
const lastRequest = ref<NestingRequest | null>(null);

const nestable = computed(() =>
  store.materials.filter((m) => m.dimension_type !== "count" && m.standard_length_mm && (m.dimension_type === "length" ? m.standard_width_mm : m.standard_width_mm)),
);
const material = computed(() => store.materials.find((m) => m.id === materialId.value));

onMounted(async () => {
  await store.fetchMaterials();
});

watch(materialId, async (id) => {
  result.value = null;
  candidates.value = null;
  selectedOrders.value = [];
  for (const k of Object.keys(extras)) delete extras[Number(k)];
  if (!id) return;
  try {
    candidates.value = await store.nestingCandidates(id);
    selectedOrders.value = candidates.value.orders.map((o) => o.order_id);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Failed";
  }
});

function rotations(): number[] | null {
  if (rotationMode.value === "all") return null;
  return rotationMode.value === "flip" ? [0, 180] : [0];
}

function buildRequest(): NestingRequest {
  return {
    material_id: materialId.value,
    items: Object.entries(extras)
      .filter(([, q]) => q > 0)
      .map(([id, q]) => ({ design_id: Number(id), quantity: Math.floor(q) })),
    order_ids: selectedOrders.value,
    spacing_mm: Number(spacing.value),
    margin_mm: Number(margin.value),
    rotations: rotations(),
  };
}

const nothingToNest = computed(() => !selectedOrders.value.length && !Object.values(extras).some((q) => q > 0));

async function run() {
  error.value = "";
  if (nothingToNest.value) {
    error.value = t("nesting.nothingToNest");
    return;
  }
  busy.value = true;
  try {
    const req = buildRequest();
    result.value = await store.runNesting(req);
    lastRequest.value = req;
    activeSheet.value = 0;
  } catch (err) {
    error.value = t("nesting.failed", { error: err instanceof ApiError ? err.message : "?" });
  } finally {
    busy.value = false;
  }
}

async function exportSheet(format: "svg" | "dxf") {
  if (!lastRequest.value) return;
  try {
    const blob = await store.exportNesting(lastRequest.value, format, activeSheet.value);
    const base = (result.value?.material_name ?? "nesting").replace(/[^\w.-]+/g, "_");
    saveBlob(blob, `${base}_${activeSheet.value + 1}.${format}`);
  } catch (err) {
    error.value = t("nesting.failed", { error: err instanceof ApiError ? err.message : "?" });
  }
}

const sheet = computed(() => result.value?.sheets[activeSheet.value] ?? null);
const reasonLabel = (r: string) => t(`nesting.unplaced.${r}`);
const wastePct = computed(() => (result.value ? Math.round((100 - result.value.utilization_pct) * 10) / 10 : 0));
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-slate-900">{{ t("nesting.title") }}</h1>
    <p class="text-sm text-slate-500 mt-1 mb-6 max-w-3xl">{{ t("nesting.subtitle") }}</p>

    <div class="grid lg:grid-cols-3 gap-6">
      <div class="space-y-4">
        <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
          <label class="block text-xs text-slate-500">{{ t("nesting.material") }}
            <select v-model.number="materialId" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mt-1">
              <option :value="0">{{ t("nesting.pickMaterial") }}</option>
              <option v-for="m in nestable" :key="m.id" :value="m.id">{{ m.name }}</option>
            </select>
          </label>
          <p v-if="!nestable.length" class="text-xs text-amber-600">{{ t("nesting.noNestableMaterial") }}</p>
          <p v-if="material" class="text-xs text-slate-500">
            {{ t("nesting.stockSheet", { l: material.standard_length_mm ?? 0, w: material.standard_width_mm ?? 0 }) }}
          </p>

          <div class="grid grid-cols-2 gap-3">
            <label class="block text-xs text-slate-500">{{ t("nesting.spacing") }}
              <input v-model.number="spacing" type="number" min="0" max="50" step="0.1" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mt-1" />
            </label>
            <label class="block text-xs text-slate-500">{{ t("nesting.margin") }}
              <input v-model.number="margin" type="number" min="0" max="100" step="0.1" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mt-1" />
            </label>
          </div>
          <label class="block text-xs text-slate-500">{{ t("nesting.rotations") }}
            <select v-model="rotationMode" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mt-1">
              <option value="all">{{ t("nesting.rot.all") }}</option>
              <option value="flip">{{ t("nesting.rot.flip") }}</option>
              <option value="fixed">{{ t("nesting.rot.fixed") }}</option>
            </select>
          </label>
        </div>

        <div v-if="candidates" class="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
          <h2 class="font-semibold text-slate-900 text-sm">{{ t("nesting.orders") }}</h2>
          <p class="text-xs text-slate-500">{{ t("nesting.ordersHint") }}</p>
          <p v-if="!candidates.orders.length" class="text-xs text-slate-400">{{ t("nesting.noOrders") }}</p>
          <label v-for="o in candidates.orders" :key="o.order_id" class="flex items-center gap-2 text-sm">
            <input v-model="selectedOrders" type="checkbox" :value="o.order_id" />
            <span class="flex-1">#{{ o.order_id }} {{ o.customer_name }}</span>
            <span class="text-xs text-slate-500">{{ t("nesting.orderParts", { n: o.part_count }) }}</span>
          </label>
        </div>

        <div v-if="candidates" class="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
          <h2 class="font-semibold text-slate-900 text-sm">{{ t("nesting.extraDesigns") }}</h2>
          <p v-if="!candidates.designs.length" class="text-xs text-slate-400">{{ t("nesting.noDesigns") }}</p>
          <div v-for="d in candidates.designs" :key="d.id" class="flex items-center gap-2 text-sm">
            <span class="flex-1 truncate">{{ d.name }}<span v-if="d.knife_model_name" class="text-xs text-slate-400"> · {{ d.knife_model_name }}</span></span>
            <input
              :value="extras[d.id] ?? 0"
              type="number" min="0" max="500" step="1" :aria-label="t('nesting.quantity')"
              class="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
              @input="extras[d.id] = Math.max(0, Math.floor(Number(($event.target as HTMLInputElement).value) || 0))"
            />
          </div>
        </div>

        <button
          class="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2"
          :disabled="!materialId || busy"
          @click="run"
        >
          {{ busy ? t("nesting.running") : t("nesting.run") }}
        </button>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>

      <div class="lg:col-span-2 space-y-4">
        <template v-if="result">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="bg-white rounded-xl border border-slate-200 p-3">
              <p class="text-xs text-slate-500">{{ t("nesting.sheetsNeeded") }}</p>
              <p class="text-2xl font-bold text-slate-900">{{ result.sheets_needed }}</p>
            </div>
            <div class="bg-white rounded-xl border border-slate-200 p-3">
              <p class="text-xs text-slate-500">{{ t("nesting.partsPlaced") }}</p>
              <p class="text-2xl font-bold text-slate-900">{{ result.placed_parts }}<span class="text-sm text-slate-400"> / {{ result.total_parts }}</span></p>
            </div>
            <div class="bg-white rounded-xl border border-slate-200 p-3">
              <p class="text-xs text-slate-500">{{ t("nesting.utilization") }}</p>
              <p class="text-2xl font-bold text-slate-900">{{ result.utilization_pct.toFixed(1) }} %</p>
              <p class="text-xs text-slate-400">{{ t("nesting.waste") }} : {{ wastePct }} % · {{ (result.waste_area_mm2 / 100).toFixed(0) }} cm²</p>
            </div>
            <div class="bg-white rounded-xl border p-3" :class="result.stock_sufficient ? 'border-emerald-200' : 'border-red-300'">
              <p class="text-xs text-slate-500">{{ t("nesting.stock") }}</p>
              <p class="text-sm font-semibold" :class="result.stock_sufficient ? 'text-emerald-600' : 'text-red-600'">
                {{ result.stock_sufficient ? t("nesting.stockOk") : t("nesting.stockShort") }}
              </p>
              <p class="text-xs text-slate-400">{{ t("nesting.stockUnits", { n: formatDecimal(result.stock_sheets_available, locale) }) }}</p>
            </div>
          </div>

          <div v-if="result.unplaced.length" class="bg-red-50 border border-red-200 rounded-xl p-3 text-sm">
            <p class="font-medium text-red-700 mb-1">{{ t("nesting.unplaced") }}</p>
            <p v-for="(u, i) in result.unplaced" :key="i" class="text-red-700 text-xs">{{ u.part_name }} ({{ u.design_name }}) — {{ reasonLabel(u.reason) }}</p>
          </div>

          <div v-if="sheet" class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <div class="flex items-center gap-2 flex-wrap">
              <button
                v-for="s in result.sheets"
                :key="s.index"
                class="px-3 py-1 rounded-lg text-sm border"
                :class="s.index === activeSheet ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-300 text-slate-600'"
                @click="activeSheet = s.index"
              >{{ t(material?.dimension_type === "length" ? "nesting.bar" : "nesting.sheet", { n: s.index + 1 }) }}</button>
              <span class="text-xs text-slate-500 ml-auto">{{ t("nesting.sheetStats", { parts: sheet.placements.length, pct: sheet.utilization_pct.toFixed(1) }) }}</span>
            </div>
            <NestingSheetVisual :sheet="sheet" :length="result.sheet_length_mm" :width="result.sheet_width_mm" :margin="result.margin_mm" />
            <p class="text-xs text-slate-400">{{ result.sheet_length_mm }} × {{ result.sheet_width_mm }} mm · {{ t("nesting.spacing") }} {{ result.spacing_mm }} · {{ t("nesting.margin") }} {{ result.margin_mm }}</p>
            <div class="flex gap-2">
              <button class="px-3 py-1.5 rounded-lg border border-slate-300 text-sm" @click="exportSheet('svg')">{{ t("nesting.exportSvg") }}</button>
              <button class="px-3 py-1.5 rounded-lg border border-slate-300 text-sm" @click="exportSheet('dxf')">{{ t("nesting.exportDxf") }}</button>
            </div>
          </div>
          <p class="text-xs text-slate-400">{{ t("nesting.note") }}</p>
        </template>
      </div>
    </div>
  </div>
</template>
