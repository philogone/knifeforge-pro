<script setup lang="ts">
import ListToolbar from "@/components/ListToolbar.vue";
import { byText, useListSearch } from "@/composables/useListSearch";
import { computed, onMounted, reactive, ref } from "vue";

import CuttingBarsVisual from "@/components/CuttingBarsVisual.vue";
import SheetGridVisual from "@/components/SheetGridVisual.vue";
import { PIECE_TYPE_SUGGESTIONS, STEEL_GRADE_SUGGESTIONS, WOOD_GRADE_SUGGESTIONS, WOOD_SPECIES_SUGGESTIONS } from "@/constants/referenceData";
import { formatDecimal, useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { CandidateOrder, CuttingPlan, DimensionType, Material, MaterialCategory, MetalType, SawType, YieldCalcResult } from "@/types";

const { t, locale } = useI18n();
const store = useAppStore();

onMounted(() => {
  store.fetchMaterials();
  store.fetchSawBlades();
});

const emptyForm = () => ({
  name: "",
  category: "blade_steel" as MaterialCategory,
  dimension_type: "length" as DimensionType,
  metal_type: null as MetalType | null,
  steel_grade: "",
  wood_species: "",
  wood_grade: "",
  piece_type: "",
  standard_length_mm: null as number | null,
  standard_width_mm: null as number | null,
  standard_thickness_mm: null as number | null,
  kerf_mm: 2,
  saw_blade_id: null as number | null,
  quantity_in_stock: 0,
  low_stock_threshold: 0,
  unit_cost: 0,
});

const form = reactive(emptyForm());
const formError = ref("");
const editingId = ref<number | null>(null);

const isMetalCategory = computed(() => form.category === "blade_steel" || form.category === "fitting");
const isWoodCategory = computed(() => form.category === "handle_material");

function onSawBladeChange() {
  if (!form.saw_blade_id) return;
  const blade = store.sawBlades.find((b) => b.id === form.saw_blade_id);
  if (blade) form.kerf_mm = blade.kerf_mm;
}

const showForm = ref(false);

function startEdit(m: Material) {
  showForm.value = true;
  editingId.value = m.id;
  Object.assign(form, {
    name: m.name,
    category: m.category,
    dimension_type: m.dimension_type,
    metal_type: m.metal_type,
    steel_grade: m.steel_grade ?? "",
    wood_species: m.wood_species ?? "",
    wood_grade: m.wood_grade ?? "",
    piece_type: m.piece_type ?? "",
    standard_length_mm: m.standard_length_mm,
    standard_width_mm: m.standard_width_mm,
    standard_thickness_mm: m.standard_thickness_mm,
    kerf_mm: m.kerf_mm,
    saw_blade_id: m.saw_blade_id,
    quantity_in_stock: m.quantity_in_stock,
    low_stock_threshold: m.low_stock_threshold,
    unit_cost: m.unit_cost,
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function cancelEdit() {
  editingId.value = null;
  showForm.value = false;
  Object.assign(form, emptyForm());
}

const submitting = ref(false);

async function submit() {
  if (submitting.value) return;
  submitting.value = true;
  formError.value = "";
  try {
    if (editingId.value) {
      const { quantity_in_stock, ...updatePayload } = form;
      await store.updateMaterial(editingId.value, updatePayload);
      cancelEdit();
    } else {
      await store.createMaterial(form);
      Object.assign(form, emptyForm());
      showForm.value = false;
    }
  } catch (err) {
    formError.value = errorMessage(err, t, "common.error");
  } finally {
    submitting.value = false;
  }
}

const deleteError = ref("");

async function removeMaterial(id: number, name: string) {
  if (!confirm(t("common.confirmDeleteNamed", { name }))) return;
  deleteError.value = "";
  try {
    await store.deleteMaterial(id);
  } catch (err) {
    deleteError.value = errorMessage(err, t, "common.deleteFailed");
  }
}

const restockOpenFor = ref<number | null>(null);
const restockForm = reactive({ quantity_delta: 0, purchase_price: null as number | null, shipping_cost: null as number | null });
const restockError = ref("");

function openRestock(materialId: number) {
  restockOpenFor.value = restockOpenFor.value === materialId ? null : materialId;
  Object.assign(restockForm, { quantity_delta: 0, purchase_price: null, shipping_cost: null });
  restockError.value = "";
}

async function submitRestock(id: number) {
  restockError.value = "";
  try {
    await store.restockMaterial(id, restockForm.quantity_delta, restockForm.purchase_price, restockForm.shipping_cost);
    restockOpenFor.value = null;
  } catch (err) {
    restockError.value = errorMessage(err, t, "common.error");
  }
}

// Saw blade mini-catalog
const showSawCatalog = ref(false);
const sawForm = reactive({ name: "", saw_type: "band_saw" as SawType, diameter_mm: null as number | null, kerf_mm: 1, notes: "" });
async function removeSaw(id: number, name: string) {
  if (!confirm(t("common.confirmDeleteNamed", { name }))) return;
  await store.deleteSawBlade(id);
}

async function addSawBlade() {
  await store.createSawBlade(sawForm);
  Object.assign(sawForm, { name: "", diameter_mm: null, kerf_mm: 1, notes: "" });
}

// Yield calculator
const yieldForm = reactive({ materialId: null as number | null, blank_length_mm: 0, blank_width_mm: null as number | null, quantity_needed: 1 });
const yieldResult = ref<YieldCalcResult | null>(null);
const yieldError = ref("");

function openYieldCalc(materialId: number) {
  yieldForm.materialId = materialId;
  yieldResult.value = null;
  yieldError.value = "";
  cutPlan.value = null;
  optimizerMaterialId.value = null;
}

async function runYieldCalc() {
  if (!yieldForm.materialId) return;
  yieldError.value = "";
  try {
    yieldResult.value = await store.yieldCalc(yieldForm.materialId, yieldForm.blank_length_mm, yieldForm.blank_width_mm, yieldForm.quantity_needed);
  } catch (err) {
    yieldError.value = errorMessage(err, t);
  }
}

const yieldBars = computed(() => {
  if (!yieldResult.value || !yieldForm.materialId) return [];
  const material = store.materials.find((m) => m.id === yieldForm.materialId);
  if (!material) return [];
  const label = `${yieldForm.blank_length_mm}mm blank`;
  const perBar = yieldResult.value.pieces_per_stock_unit;
  const bars = [];
  let remaining = yieldForm.quantity_needed;
  for (let i = 0; i < yieldResult.value.stock_units_needed; i++) {
    const count = Math.min(perBar, remaining);
    bars.push({
      pieces: Array.from({ length: count }, () => ({ length: yieldForm.blank_length_mm, label })),
      waste: material.dimension_type === "length" ? yieldResult.value!.waste_per_stock_unit : 0,
    });
    remaining -= count;
  }
  return bars;
});

// Cutting optimizer (cross-order) — pick which draft/confirmed orders to
// include before running, since a confirmed order is often the one about
// to actually go into production.
const cutPlan = ref<CuttingPlan | null>(null);
const cutError = ref("");
const optimizerMaterialId = ref<number | null>(null);
const candidates = ref<CandidateOrder[]>([]);
const selectedOrderIds = ref<Set<number>>(new Set());

async function openOptimizer(materialId: number) {
  optimizerMaterialId.value = materialId;
  yieldForm.materialId = null;
  yieldResult.value = null;
  cutPlan.value = null;
  cutError.value = "";
  candidates.value = await store.cuttingCandidates(materialId);
  selectedOrderIds.value = new Set(candidates.value.map((c) => c.order_id));
}

function toggleCandidate(orderId: number) {
  if (selectedOrderIds.value.has(orderId)) selectedOrderIds.value.delete(orderId);
  else selectedOrderIds.value.add(orderId);
}

async function runOptimizer(materialId: number) {
  cutError.value = "";
  try {
    cutPlan.value = await store.cuttingOptimizer(materialId, Array.from(selectedOrderIds.value));
  } catch (err) {
    cutError.value = errorMessage(err, t);
  }
}
const cutBarsForVisual = computed(() => {
  if (!cutPlan.value) return [];
  return cutPlan.value.bars.map((bar) => ({
    pieces: bar.pieces.map((p) => ({ length: p.length_mm, label: `${p.knife_model_name} — ${p.customer_name}` })),
    waste: bar.waste_mm,
  }));
});

/** stock at or under its threshold: the one state on this page that needs the maker's eye */
function isLow(m: Material) {
  return m.low_stock_threshold > 0 && m.quantity_in_stock <= m.low_stock_threshold;
}

function unitFor(dimension_type: DimensionType, n = 2) {
  return dimension_type === "length" ? "mm" : dimension_type === "area" ? "mm²" : t(n > 1 ? "common.unitMany" : "common.unitOne");
}

// ---- search and sort
const list = useListSearch(
  () => store.materials,
  (m) => [m.name, m.steel_grade, m.wood_species, m.wood_grade, m.piece_type, t(`materials.category.${m.category}`)],
  [
    { key: "name", label: "", compare: (a, b) => byText(a.name, b.name) },
    { key: "low", label: "", compare: (a, b) => Number(isLow(b)) - Number(isLow(a)) || byText(a.name, b.name) },
    { key: "category", label: "", compare: (a, b) => byText(t(`materials.category.${a.category}`), t(`materials.category.${b.category}`)) || byText(a.name, b.name) },
  ],
);
const sortOptions = computed(() => [
  { key: "name", label: t("list.sort.name") },
  { key: "low", label: t("list.sort.lowStockFirst") },
  { key: "category", label: t("list.sort.category") },
]);
</script>

<template>
  <div class="page max-w-5xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("materials.title") }}</h1>
        <p class="page-lead">{{ t("materials.lead") }}</p>
      </div>
      <button v-if="!showForm" class="btn btn-primary" @click="showForm = true">+ {{ t("materials.addTitle") }}</button>
    </header>
    <p v-if="deleteError" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ deleteError }}</p>

    <!-- Add / edit material -->
    <div v-if="showForm || editingId" class="sheet p-5 mb-8">
      <h2 class="sheet-title mb-4">{{ editingId ? t("materials.editTitle") : t("materials.addTitle") }}</h2>
      <form class="space-y-3" @submit.prevent="submit">
        <div class="field-grid grid grid-cols-2 md:grid-cols-3 gap-3">
          <div class="col-span-2">
            <label class="field-label" for="materials-f1">{{ t("materials.name") }}</label>
            <input id="materials-f1" v-model="form.name" required class="input w-full" />
          </div>
          <div>
            <label class="field-label" for="materials-f2">{{ t("materials.category") }}</label>
            <select id="materials-f2" v-model="form.category" class="input w-full">
              <option value="blade_steel">{{ t("materials.category.blade_steel") }}</option>
              <option value="handle_material">{{ t("materials.category.handle_material") }}</option>
              <option value="fitting">{{ t("materials.category.fitting") }}</option>
              <option value="hardware">{{ t("materials.category.hardware") }}</option>
              <option value="consumable">{{ t("materials.category.consumable") }}</option>
            </select>
          </div>
          <div>
            <label class="field-label" for="materials-f3">{{ t("materials.dimensionType") }}</label>
            <select id="materials-f3" v-model="form.dimension_type" class="input w-full">
              <option value="length">{{ t("materials.dimensionType.length") }}</option>
              <option value="area">{{ t("materials.dimensionType.area") }}</option>
              <option value="count">{{ t("materials.dimensionType.count") }}</option>
            </select>
          </div>
          <div>
            <label class="field-label" for="materials-f4">{{ t("materials.pieceType") }}</label>
            <input id="materials-f4" v-model="form.piece_type" list="piece-types" :placeholder="t('materials.pieceType.example')" class="input w-full" />
            <datalist id="piece-types"><option v-for="p in PIECE_TYPE_SUGGESTIONS" :key="p" :value="p" /></datalist>
          </div>

          <template v-if="isMetalCategory">
            <div>
              <label class="field-label" for="materials-f5">{{ t("materials.metalType") }}</label>
              <select id="materials-f5" v-model="form.metal_type" class="input w-full">
                <option :value="null">{{ t("materials.metalType.none") }}</option>
                <option value="stainless_steel">{{ t("materials.metalType.stainless_steel") }}</option>
                <option value="carbon_steel">{{ t("materials.metalType.carbon_steel") }}</option>
                <option value="titanium">{{ t("materials.metalType.titanium") }}</option>
                <option value="mokume_gane">{{ t("materials.metalType.mokume_gane") }}</option>
                <option value="brass">{{ t("materials.metalType.brass") }}</option>
                <option value="copper">{{ t("materials.metalType.copper") }}</option>
                <option value="nickel_silver">{{ t("materials.metalType.nickel_silver") }}</option>
                <option value="other">{{ t("materials.metalType.other") }}</option>
              </select>
            </div>
            <div>
              <label class="field-label" for="materials-f6">{{ t("materials.steelGrade") }}</label>
              <input id="materials-f6" v-model="form.steel_grade" list="steel-grades" :placeholder="t('materials.steelGrade.example')" class="input w-full" />
              <datalist id="steel-grades"><option v-for="g in STEEL_GRADE_SUGGESTIONS" :key="g" :value="g" /></datalist>
            </div>
          </template>

          <template v-if="isWoodCategory">
            <div>
              <label class="field-label" for="materials-f7">{{ t("materials.woodSpecies") }}</label>
              <input id="materials-f7" v-model="form.wood_species" list="wood-species" class="input w-full" />
              <datalist id="wood-species"><option v-for="s in WOOD_SPECIES_SUGGESTIONS" :key="s" :value="s" /></datalist>
            </div>
            <div>
              <label class="field-label" for="materials-f8">{{ t("materials.woodGrade") }}</label>
              <input id="materials-f8" v-model="form.wood_grade" list="wood-grades" class="input w-full" />
              <datalist id="wood-grades"><option v-for="g in WOOD_GRADE_SUGGESTIONS" :key="g" :value="g" /></datalist>
            </div>
          </template>

          <div>
            <label class="field-label" for="materials-f9">{{ t("materials.length") }}</label>
            <input id="materials-f9" v-model.number="form.standard_length_mm" type="number" step="any" class="input w-full" />
          </div>
          <div v-if="form.dimension_type !== 'length'">
            <label class="field-label" for="materials-f10">{{ t("materials.width") }}</label>
            <input id="materials-f10" v-model.number="form.standard_width_mm" type="number" step="any" class="input w-full" />
          </div>
          <div>
            <label class="field-label" for="materials-f11">{{ t("materials.thickness") }}</label>
            <input id="materials-f11" v-model.number="form.standard_thickness_mm" type="number" step="any" class="input w-full" />
          </div>

          <div v-if="form.dimension_type === 'length'">
            <label class="field-label" for="materials-f12">{{ t("materials.sawBlade") }}</label>
            <select id="materials-f12" v-model="form.saw_blade_id" class="input w-full" @change="onSawBladeChange">
              <option :value="null">{{ t("materials.sawBlade.none") }}</option>
              <option v-for="b in store.sawBlades" :key="b.id" :value="b.id">{{ b.name }} ({{ formatDecimal(b.kerf_mm, locale) }} mm)</option>
            </select>
          </div>
          <div v-if="form.dimension_type === 'length'">
            <label class="field-label" for="materials-f13">{{ t("materials.kerf") }}</label>
            <input id="materials-f13" v-model.number="form.kerf_mm" type="number" step="any" class="input w-full" />
          </div>

          <div v-if="!editingId">
            <label class="field-label" for="materials-f14">{{ t("materials.initialStock") }}</label>
            <input id="materials-f14" v-model.number="form.quantity_in_stock" type="number" step="any" class="input w-full" />
          </div>
          <div>
            <label class="field-label" for="materials-f15">{{ t("materials.lowStockThreshold") }}</label>
            <input id="materials-f15" v-model.number="form.low_stock_threshold" type="number" step="any" class="input w-full" />
          </div>
          <div>
            <label class="field-label" for="materials-f16">{{ t("materials.unitCost", { unit: unitFor(form.dimension_type) }) }}</label>
            <input id="materials-f16" v-model.number="form.unit_cost" type="number" step="any" aria-describedby="unit-cost-hint" class="input w-full" />
          </div>
        </div>
        <p id="unit-cost-hint" class="sheet-hint max-w-prose">{{ t("materials.unitCost.hint") }}</p>
        <p v-if="formError" role="alert" class="text-sm text-red-700">{{ formError }}</p>
        <div class="flex gap-2">
          <button type="submit" class="btn btn-primary" :disabled="submitting">
            {{ editingId ? t("common.saveChanges") : t("common.add") }}
          </button>
          <button type="button" class="btn btn-outline" @click="cancelEdit">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>

    <ListToolbar
      v-if="list.total.value"
      v-model:query="list.query.value"
      v-model:sort="list.sortKey.value"
      :placeholder="t('list.search.materials')"
      :sorts="sortOptions"
      :shown="list.visible.value.length"
      :total="list.total.value"
    ></ListToolbar>
    <div class="space-y-3">
      <p v-if="list.total.value && !list.visible.value.length" class="sheet p-6 text-sm text-slate-600">{{ t("list.noMatch") }}</p>
      <div v-for="m in list.visible.value" :key="m.id" class="sheet p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-2 flex-wrap min-w-0">
            <span class="font-semibold text-slate-900">{{ m.name }}</span>
            <span class="tag tag-accent">{{ t(`materials.category.${m.category}`) }}</span>
            <span v-if="m.is_mock" class="tag tag-neutral">{{ t("common.demo") }}</span>
          </div>
          <div class="flex gap-4 shrink-0">
            <button class="link-action" @click="startEdit(m)">{{ t("common.edit") }}</button>
            <button class="link-danger" @click="removeMaterial(m.id, m.name)">{{ t("common.delete") }}</button>
          </div>
        </div>

        <p class="mt-1 text-xs text-slate-500">
          {{
            [
              m.steel_grade,
              m.wood_species ? [m.wood_species, m.wood_grade].filter(Boolean).join(" · ") : null,
              m.piece_type,
              m.standard_length_mm
                ? [m.standard_length_mm, m.standard_width_mm, m.standard_thickness_mm].filter((v) => v).map((v) => formatDecimal(v!, locale)).join(" × ") + " mm"
                : null,
              m.saw_blade_name,
            ]
              .filter(Boolean)
              .join(" · ")
          }}
        </p>

        <dl class="mt-3 flex items-baseline gap-x-8 gap-y-1 flex-wrap text-sm">
          <div class="flex items-baseline gap-2">
            <dt class="text-slate-500">{{ t("materials.stock") }}</dt>
            <dd class="font-medium tabular-nums" :class="isLow(m) ? 'text-amber-800' : 'text-slate-900'">
              {{ formatDecimal(m.quantity_in_stock, locale, 3) }} {{ unitFor(m.dimension_type, m.quantity_in_stock) }}
            </dd>
            <span v-if="isLow(m)" class="tag tag-warning font-medium">{{ t("materials.lowStock") }}</span>
          </div>
          <div class="flex items-baseline gap-2">
            <dt class="text-slate-500">{{ t("materials.threshold") }}</dt>
            <dd class="tabular-nums text-slate-700">{{ formatDecimal(m.low_stock_threshold, locale, 3) }} {{ unitFor(m.dimension_type, m.low_stock_threshold) }}</dd>
          </div>
          <div class="flex items-baseline gap-2">
            <dt class="text-slate-500">{{ t("materials.landedCost") }}</dt>
            <dd class="tabular-nums text-slate-700">{{ formatDecimal(m.unit_cost, locale, 6) }} €/{{ unitFor(m.dimension_type, 1) }}</dd>
          </div>
        </dl>
        <div class="mt-3 pt-3 border-t border-slate-100 flex items-center gap-5 flex-wrap">
          <button class="link-action" @click="openRestock(m.id)">{{ t("materials.restock") }}</button>
          <button v-if="m.dimension_type !== 'count'" class="link-action" @click="openYieldCalc(m.id)">{{ t("materials.yieldCalculator") }}</button>
          <button v-if="m.dimension_type === 'length'" class="link-action" @click="openOptimizer(m.id)">{{ t("materials.cuttingOptimizer") }}</button>
        </div>

        <div v-if="restockOpenFor === m.id" class="mt-3 border-t border-slate-100 pt-3">
          <p class="text-xs text-slate-500 mb-2">{{ t("materials.restock.hint") }}</p>
          <div class="flex items-end gap-2 flex-wrap">
            <div>
              <label class="field-label" for="materials-f17">{{ t("materials.restock.quantity", { unit: unitFor(m.dimension_type) }) }}</label>
              <input id="materials-f17" v-model.number="restockForm.quantity_delta" type="number" step="any" class="w-36 input-sm" />
            </div>
            <div>
              <label class="field-label" for="materials-f18">{{ t("materials.restock.purchasePrice") }}</label>
              <input id="materials-f18" v-model.number="restockForm.purchase_price" type="number" step="any" min="0" class="w-32 input-sm" />
            </div>
            <div>
              <label class="field-label" for="materials-f19">{{ t("materials.restock.shippingCost") }}</label>
              <input id="materials-f19" v-model.number="restockForm.shipping_cost" type="number" step="any" min="0" class="w-32 input-sm" />
            </div>
            <button class="btn btn-secondary btn-sm" @click="submitRestock(m.id)">{{ t("materials.restock.confirm") }}</button>
          </div>
          <p v-if="restockError" class="text-sm text-red-600 mt-2">{{ restockError }}</p>
        </div>

        <div v-if="yieldForm.materialId === m.id" class="mt-3 border-t border-slate-100 pt-3">
          <div class="flex items-end gap-2 flex-wrap">
            <div>
              <label class="field-label" for="materials-f20">{{ t("materials.blankLength") }}</label>
              <input id="materials-f20" v-model.number="yieldForm.blank_length_mm" type="number" step="any" class="w-40 input-sm" />
            </div>
            <div v-if="m.dimension_type === 'area'">
              <label class="field-label" for="materials-f21">{{ t("materials.blankWidth") }}</label>
              <input id="materials-f21" v-model.number="yieldForm.blank_width_mm" type="number" step="any" class="w-40 input-sm" />
            </div>
            <div>
              <label class="field-label" for="materials-f22">{{ t("materials.quantityNeeded") }}</label>
              <input id="materials-f22" v-model.number="yieldForm.quantity_needed" type="number" min="1" class="w-32 input-sm" />
            </div>
            <button class="text-sm bg-slate-800 text-paper rounded-lg px-3 py-1.5" @click="runYieldCalc">{{ t("materials.calculate") }}</button>
          </div>
          <p v-if="yieldError" class="text-sm text-red-600 mt-2">{{ yieldError }}</p>
          <div v-if="yieldResult" class="mt-3">
            <div class="text-sm text-slate-700 grid grid-cols-2 gap-x-6 gap-y-1 mb-3">
              <span>{{ t("materials.piecesPerStockUnit") }}{{ t("common.colon") }} <strong>{{ yieldResult.pieces_per_stock_unit }}</strong></span>
              <span>{{ t("materials.stockUnitsNeeded") }}{{ t("common.colon") }} <strong>{{ yieldResult.stock_units_needed }}</strong></span>
              <span>{{ t("materials.wastePerStockUnit") }}{{ t("common.colon") }} <strong class="tabular-nums">{{ formatDecimal(yieldResult.waste_per_stock_unit, locale) }} {{ yieldResult.unit }}</strong></span>
              <span>{{ t("materials.wastePercentage") }}{{ t("common.colon") }} <strong class="tabular-nums">{{ formatDecimal(yieldResult.waste_percentage, locale, 1) }} %</strong></span>
            </div>
            <CuttingBarsVisual
              v-if="m.dimension_type === 'length' && m.standard_length_mm"
              :stock-length="m.standard_length_mm"
              :kerf="m.kerf_mm"
              :bars="yieldBars"
            />
            <SheetGridVisual
              v-if="m.dimension_type === 'area' && m.standard_length_mm && m.standard_width_mm && yieldForm.blank_width_mm"
              :sheet-length="m.standard_length_mm"
              :sheet-width="m.standard_width_mm"
              :blank-length="yieldForm.blank_length_mm"
              :blank-width="yieldForm.blank_width_mm"
              :cols="yieldResult.grid_cols ?? 0"
              :rows="yieldResult.grid_rows ?? 0"
              :rotated="yieldResult.rotated"
            />
          </div>
        </div>

        <div v-if="optimizerMaterialId === m.id" class="mt-3 border-t border-slate-100 pt-3">
          <div v-if="candidates.length === 0" class="text-sm text-slate-500">{{ t("materials.optimizer.noDraftDemand") }}</div>
          <template v-else>
            <p class="text-xs text-slate-500 mb-2">{{ t("materials.optimizer.pickOrders") }}</p>
            <ul class="space-y-1 mb-3">
              <li v-for="c in candidates" :key="c.order_id" class="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  :checked="selectedOrderIds.has(c.order_id)"
                  @change="toggleCandidate(c.order_id)"
                />
                <span class="text-slate-800">{{ c.customer_name }}</span>
                <span class="text-xs rounded px-1.5 py-0.5" :class="c.status === 'confirmed' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'">{{ t(`orders.status.${c.status}`) }}</span>
                <span class="text-slate-500">{{ c.piece_count }} {{ t("materials.optimizer.pieces") }}, {{ formatDecimal(c.total_length_mm, locale) }} mm</span>
              </li>
            </ul>
            <button class="text-sm bg-slate-800 text-paper rounded-lg px-3 py-1.5" @click="runOptimizer(m.id)">{{ t("materials.optimizer.run") }}</button>
          </template>

          <p v-if="cutError" class="text-sm text-red-600 mt-2">{{ cutError }}</p>
          <div v-if="cutPlan && cutPlan.material_id === m.id" class="mt-3">
            <div class="text-sm text-slate-700 grid grid-cols-3 gap-x-6 gap-y-1 mb-3">
              <span>{{ t("materials.optimizer.barsNeeded") }}{{ t("common.colon") }} <strong>{{ cutPlan.bars_needed }}</strong></span>
              <span>{{ t("materials.optimizer.totalPieces") }}{{ t("common.colon") }} <strong>{{ cutPlan.total_pieces }}</strong></span>
              <span>{{ t("materials.optimizer.totalWaste") }}{{ t("common.colon") }} <strong class="tabular-nums">{{ formatDecimal(cutPlan.total_waste_mm, locale) }} mm ({{ formatDecimal(cutPlan.waste_percentage, locale, 1) }} %)</strong></span>
            </div>
            <CuttingBarsVisual :stock-length="cutPlan.stock_length_mm" :kerf="cutPlan.kerf_mm" :bars="cutBarsForVisual" />
          </div>
        </div>
      </div>
    </div>

    <!-- Saw blade catalog -->
    <div class="sheet p-4 mt-8">
      <button class="flex items-center justify-between w-full text-left" @click="showSawCatalog = !showSawCatalog">
        <span class="sheet-title">{{ t("materials.sawBladeCatalog") }}</span>
        <span class="text-sm text-slate-500">{{ store.sawBlades.length }} · {{ showSawCatalog ? "−" : "+" }}</span>
      </button>
      <div v-if="showSawCatalog" class="mt-3">
        <p class="text-xs text-slate-500 mb-3">{{ t("materials.sawBladeCatalog.hint") }}</p>
        <form class="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3" @submit.prevent="addSawBlade">
          <input v-model="sawForm.name" :placeholder="t('common.name')" :aria-label="t('common.name')" required class="input-sm" />
          <select v-model="sawForm.saw_type" :aria-label="t('materials.sawTypeLabel')" class="input-sm">
            <option value="band_saw">{{ t("materials.sawType.band_saw") }}</option>
            <option value="circular_saw">{{ t("materials.sawType.circular_saw") }}</option>
            <option value="abrasive_cutoff">{{ t("materials.sawType.abrasive_cutoff") }}</option>
            <option value="hacksaw">{{ t("materials.sawType.hacksaw") }}</option>
            <option value="other">{{ t("materials.sawType.other") }}</option>
          </select>
          <input v-model.number="sawForm.diameter_mm" type="number" step="any" :placeholder="t('materials.diameter')" :aria-label="t('materials.diameter')" class="input-sm" />
          <input v-model.number="sawForm.kerf_mm" type="number" step="any" required :placeholder="t('materials.kerf')" :aria-label="t('materials.kerf')" class="input-sm" />
          <button type="submit" class="btn btn-secondary btn-sm">{{ t("materials.addSawBlade") }}</button>
        </form>
        <ul class="text-sm text-slate-700 divide-y divide-slate-100">
          <li v-for="b in store.sawBlades" :key="b.id" class="flex items-center justify-between py-1.5">
            <span>{{ b.name }} — {{ t(`materials.sawType.${b.saw_type}`) }}, {{ formatDecimal(b.kerf_mm, locale) }} mm<span v-if="b.diameter_mm"> (Ø {{ formatDecimal(b.diameter_mm, locale) }} mm)</span></span>
            <button class="link-danger text-xs" @click="removeSaw(b.id, b.name)">{{ t("common.delete") }}</button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
