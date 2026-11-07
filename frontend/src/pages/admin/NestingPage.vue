<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import NestingSheetVisual from "@/components/NestingSheetVisual.vue";
import { saveBlob } from "@/composables/useApi";
import { formatDecimal, useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { NestingCandidates, NestingRequest, NestingResult } from "@/types";

const { t, locale, num } = useI18n();
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
    error.value = errorMessage(err, t, "common.error");
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
    error.value = t("nesting.failed", { error: errorMessage(err, t) });
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
    error.value = t("nesting.failed", { error: errorMessage(err, t) });
  }
}

const sheet = computed(() => result.value?.sheets[activeSheet.value] ?? null);
const reasonLabel = (r: string) => t(`nesting.unplaced.${r}`);
const wastePct = computed(() => (result.value ? Math.round((100 - result.value.utilization_pct) * 10) / 10 : 0));
</script>

<template>
  <div class="page max-w-6xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("nesting.title") }}</h1>
        <p class="page-lead max-w-3xl">{{ t("nesting.subtitle") }}</p>
      </div>
    </header>

    <div class="grid lg:grid-cols-3 gap-6">
      <div class="space-y-4">
        <div class="sheet p-4 space-y-3">
          <label class="field-label">{{ t("nesting.material") }}
            <select v-model.number="materialId" class="input w-full mt-1">
              <option :value="0">{{ t("nesting.pickMaterial") }}</option>
              <option v-for="m in nestable" :key="m.id" :value="m.id">{{ m.name }}</option>
            </select>
          </label>
          <p v-if="!nestable.length" class="text-xs text-amber-800">{{ t("nesting.noNestableMaterial") }}</p>
          <p v-if="material" class="text-xs text-slate-500">
            {{ t("nesting.stockSheet", { l: material.standard_length_mm ?? 0, w: material.standard_width_mm ?? 0 }) }}
          </p>

          <div class="grid grid-cols-2 gap-3">
            <label class="field-label">{{ t("nesting.spacing") }}
              <input v-model.number="spacing" type="number" min="0" max="50" step="0.1" class="input w-full mt-1" />
            </label>
            <label class="field-label">{{ t("nesting.margin") }}
              <input v-model.number="margin" type="number" min="0" max="100" step="0.1" class="input w-full mt-1" />
            </label>
          </div>
          <label class="field-label">{{ t("nesting.rotations") }}
            <select v-model="rotationMode" class="input w-full mt-1">
              <option value="all">{{ t("nesting.rot.all") }}</option>
              <option value="flip">{{ t("nesting.rot.flip") }}</option>
              <option value="fixed">{{ t("nesting.rot.fixed") }}</option>
            </select>
          </label>
        </div>

        <div v-if="candidates" class="sheet p-4 space-y-2">
          <h2 class="sheet-title text-sm">{{ t("nesting.orders") }}</h2>
          <p class="text-xs text-slate-500">{{ t("nesting.ordersHint") }}</p>
          <p v-if="!candidates.orders.length" class="text-xs text-slate-500">{{ t("nesting.noOrders") }}</p>
          <label v-for="o in candidates.orders" :key="o.order_id" class="flex items-center gap-2 text-sm">
            <input v-model="selectedOrders" type="checkbox" :value="o.order_id" />
            <span class="flex-1">#{{ o.order_id }} {{ o.customer_name }}</span>
            <span class="text-xs text-slate-500">{{ t("nesting.orderParts", { n: o.part_count }) }}</span>
          </label>
          <div v-if="candidates.unlinked?.length" class="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 space-y-1">
            <p class="font-medium">{{ t("nesting.unlinkedTitle") }}</p>
            <p v-for="u in candidates.unlinked" :key="`${u.order_id}-${u.knife_model_id}`">
              #{{ u.order_id }} {{ u.customer_name }} · {{ u.quantity }} × {{ u.knife_model_name }} —
              <router-link :to="`/knife-models/${u.knife_model_id}`" class="underline underline-offset-2">{{ t("nesting.unlinkedLink") }}</router-link>
            </p>
          </div>
        </div>

        <div v-if="candidates" class="sheet p-4 space-y-2">
          <h2 class="sheet-title text-sm">{{ t("nesting.extraDesigns") }}</h2>
          <p v-if="!candidates.designs.length" class="text-xs text-slate-500">{{ t("nesting.noDesigns") }}</p>
          <div v-for="d in candidates.designs" :key="d.id" class="flex items-center gap-2 text-sm">
            <span class="flex-1 truncate">{{ d.name }}<span v-if="d.knife_model_name" class="text-xs text-slate-500"> · {{ d.knife_model_name }}</span></span>
            <input
              :value="extras[d.id] ?? 0"
              type="number" min="0" max="500" step="1" :aria-label="t('nesting.quantity')"
              class="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
              @input="extras[d.id] = Math.max(0, Math.floor(Number(($event.target as HTMLInputElement).value) || 0))"
            />
          </div>
        </div>

        <button
          class="w-full btn btn-primary"
          :disabled="!materialId || busy"
          @click="run"
        >
          {{ busy ? t("nesting.running") : t("nesting.run") }}
        </button>
        <p v-if="!materialId" class="text-xs text-slate-500">{{ t("nesting.pickMaterialFirst") }}</p>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>

      <div class="lg:col-span-2 space-y-4">
        <template v-if="result">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="sheet p-3">
              <p class="text-xs text-slate-500">{{ t("nesting.sheetsNeeded") }}</p>
              <p class="text-2xl font-semibold tabular-nums text-slate-900">{{ result.sheets_needed }}</p>
            </div>
            <div class="sheet p-3">
              <p class="text-xs text-slate-500">{{ t("nesting.partsPlaced") }}</p>
              <p class="text-2xl font-semibold tabular-nums text-slate-900">{{ result.placed_parts }}<span class="text-sm font-normal text-slate-500"> / {{ result.total_parts }}</span></p>
            </div>
            <div class="sheet p-3">
              <p class="text-xs text-slate-500">{{ t("nesting.utilization") }}</p>
              <p class="text-2xl font-semibold tabular-nums text-slate-900">{{ num(result.utilization_pct) }} %</p>
              <p class="text-xs text-slate-500">{{ t("nesting.waste") }}{{ t("common.colon") }} {{ wastePct }} % · {{ num(result.waste_area_mm2 / 100, 0) }} cm²</p>
            </div>
            <div class="sheet p-3" :class="result.stock_sufficient ? '' : 'border-red-300 bg-red-50'">
              <p class="text-xs text-slate-500">{{ t("nesting.stock") }}</p>
              <p class="mt-1 text-sm font-semibold" :class="result.stock_sufficient ? 'text-green-700' : 'text-red-700'">
                {{ result.stock_sufficient ? t("nesting.stockOk") : t("nesting.stockShort") }}
              </p>
              <p class="text-xs text-slate-500">{{ t("nesting.stockUnits", { n: formatDecimal(result.stock_sheets_available, locale) }) }}</p>
            </div>
          </div>

          <div v-if="result.unplaced.length" class="bg-red-50 border border-red-200 rounded-xl p-3 text-sm">
            <p class="font-medium text-red-700 mb-1">{{ t("nesting.unplaced") }}</p>
            <p v-for="(u, i) in result.unplaced" :key="i" class="text-red-700 text-xs">{{ u.part_name }} ({{ u.design_name }}) — {{ reasonLabel(u.reason) }}</p>
          </div>

          <div v-if="sheet" class="sheet p-4 space-y-3">
            <div class="flex items-center gap-2 flex-wrap min-w-0">
              <button
                v-for="s in result.sheets"
                :key="s.index"
                class="px-3 py-1 rounded-lg text-sm border tabular-nums transition-colors"
                :aria-pressed="s.index === activeSheet"
                :class="s.index === activeSheet ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
                @click="activeSheet = s.index"
              >{{ t(material?.dimension_type === "length" ? "nesting.bar" : "nesting.sheet", { n: s.index + 1 }) }}</button>
              <span class="text-xs text-slate-500 ml-auto">{{ t("nesting.sheetStats", { parts: sheet.placements.length, pct: num(sheet.utilization_pct) }) }}</span>
            </div>
            <NestingSheetVisual :sheet="sheet" :length="result.sheet_length_mm" :width="result.sheet_width_mm" :margin="result.margin_mm" />
            <p class="text-xs text-slate-500 tabular-nums">{{ formatDecimal(result.sheet_length_mm, locale) }} × {{ formatDecimal(result.sheet_width_mm, locale) }} mm · {{ t("nesting.spacing") }} {{ formatDecimal(result.spacing_mm, locale) }} · {{ t("nesting.margin") }} {{ formatDecimal(result.margin_mm, locale) }}</p>
            <div class="flex gap-2">
              <button class="btn btn-outline btn-sm" @click="exportSheet('svg')">{{ t("nesting.exportSvg") }}</button>
              <button class="btn btn-outline btn-sm" @click="exportSheet('dxf')">{{ t("nesting.exportDxf") }}</button>
            </div>
          </div>
          <p class="text-xs text-slate-500">{{ t("nesting.note") }}</p>
        </template>
        <div v-else class="sheet border-dashed bg-paper/70 min-h-[22rem] p-8 flex flex-col items-center justify-center text-center">
          <svg width="220" height="110" viewBox="0 0 220 110" fill="none" aria-hidden="true" class="mb-5">
            <rect x="1" y="1" width="218" height="108" rx="3" stroke="rgb(var(--slate-300))" stroke-dasharray="4 4" />
            <path d="M14 24h70l8-8h40c14 0 24 6 32 16-8 10-20 14-34 14H92l-8-8H14z" fill="rgb(var(--slate-500) / 0.12)" stroke="rgb(var(--slate-600))" stroke-width="1.2" />
            <path d="M206 86h-70l-8 8H88c-14 0-24-6-32-16 8-10 20-14 34-14h38l8 8h70z" fill="rgb(var(--slate-500) / 0.12)" stroke="rgb(var(--slate-600))" stroke-width="1.2" />
          </svg>
          <p class="sheet-title">{{ t("nesting.emptyTitle") }}</p>
          <p class="mt-1 text-sm text-slate-600 max-w-sm">{{ t(materialId ? "nesting.emptyRun" : "nesting.emptyPick") }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
