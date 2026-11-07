<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import CuttingBarsVisual from "@/components/CuttingBarsVisual.vue";
import SheetGridVisual from "@/components/SheetGridVisual.vue";
import { PIECE_TYPE_SUGGESTIONS, STEEL_GRADE_SUGGESTIONS, WOOD_GRADE_SUGGESTIONS, WOOD_SPECIES_SUGGESTIONS } from "@/constants/referenceData";
import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { CandidateOrder, CuttingPlan, DimensionType, Material, MaterialCategory, MetalType, SawType, YieldCalcResult } from "@/types";

const { t } = useI18n();
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

function startEdit(m: Material) {
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
  Object.assign(form, emptyForm());
}

async function submit() {
  formError.value = "";
  try {
    if (editingId.value) {
      const { quantity_in_stock, ...updatePayload } = form;
      await store.updateMaterial(editingId.value, updatePayload);
      cancelEdit();
    } else {
      await store.createMaterial(form);
      Object.assign(form, emptyForm());
    }
  } catch (err) {
    formError.value = err instanceof ApiError ? err.message : t("common.error");
  }
}

const deleteError = ref("");

async function removeMaterial(id: number, name: string) {
  if (!confirm(t("common.confirmDeleteNamed", { name }))) return;
  deleteError.value = "";
  try {
    await store.deleteMaterial(id);
  } catch (err) {
    deleteError.value = err instanceof ApiError ? err.message : t("common.deleteFailed");
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
    restockError.value = err instanceof ApiError ? err.message : t("common.error");
  }
}

// Saw blade mini-catalog
const showSawCatalog = ref(false);
const sawForm = reactive({ name: "", saw_type: "band_saw" as SawType, diameter_mm: null as number | null, kerf_mm: 1, notes: "" });
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
    yieldError.value = err instanceof ApiError ? err.message : "Calculation failed";
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
    cutError.value = err instanceof ApiError ? err.message : "Optimization failed";
  }
}
const cutBarsForVisual = computed(() => {
  if (!cutPlan.value) return [];
  return cutPlan.value.bars.map((bar) => ({
    pieces: bar.pieces.map((p) => ({ length: p.length_mm, label: `${p.knife_model_name} — ${p.customer_name}` })),
    waste: bar.waste_mm,
  }));
});

function unitFor(dimension_type: DimensionType) {
  return dimension_type === "length" ? "mm" : dimension_type === "area" ? "mm²" : t("common.unitShort");
}
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-6">{{ t("materials.title") }}</h1>
    <p v-if="deleteError" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ deleteError }}</p>

    <!-- Saw blade catalog -->
    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-6">
      <button class="flex items-center justify-between w-full text-left" @click="showSawCatalog = !showSawCatalog">
        <span class="font-semibold text-slate-900">{{ t("materials.sawBladeCatalog") }}</span>
        <span class="text-slate-500 text-sm">{{ showSawCatalog ? "−" : "+" }}</span>
      </button>
      <div v-if="showSawCatalog" class="mt-3">
        <p class="text-xs text-slate-500 mb-3">{{ t("materials.sawBladeCatalog.hint") }}</p>
        <form class="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3" @submit.prevent="addSawBlade">
          <input v-model="sawForm.name" :placeholder="t('common.name')" required class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
          <select v-model="sawForm.saw_type" class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
            <option value="band_saw">{{ t("materials.sawType.band_saw") }}</option>
            <option value="circular_saw">{{ t("materials.sawType.circular_saw") }}</option>
            <option value="abrasive_cutoff">{{ t("materials.sawType.abrasive_cutoff") }}</option>
            <option value="hacksaw">{{ t("materials.sawType.hacksaw") }}</option>
            <option value="other">{{ t("materials.sawType.other") }}</option>
          </select>
          <input v-model.number="sawForm.diameter_mm" type="number" step="any" :placeholder="t('materials.diameter')" class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
          <input v-model.number="sawForm.kerf_mm" type="number" step="any" required :placeholder="t('materials.kerf')" class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
          <button type="submit" class="bg-slate-800 text-white text-sm rounded-lg px-3 py-1.5">{{ t("materials.addSawBlade") }}</button>
        </form>
        <ul class="text-sm text-slate-600 space-y-1">
          <li v-for="b in store.sawBlades" :key="b.id" class="flex items-center justify-between">
            <span>{{ b.name }} — {{ t(`materials.sawType.${b.saw_type}`) }}, {{ b.kerf_mm }}mm<span v-if="b.diameter_mm"> (Ø{{ b.diameter_mm }}mm)</span></span>
            <button class="text-red-600 text-xs" @click="store.deleteSawBlade(b.id)">{{ t("common.delete") }}</button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Add / edit material -->
    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-8">
      <h2 class="font-semibold text-slate-900 mb-3">{{ editingId ? t("materials.editTitle") : t("materials.addTitle") }}</h2>
      <form class="space-y-3" @submit.prevent="submit">
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div class="col-span-2">
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.name") }}</label>
            <input v-model="form.name" required class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.category") }}</label>
            <select v-model="form.category" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="blade_steel">{{ t("materials.category.blade_steel") }}</option>
              <option value="handle_material">{{ t("materials.category.handle_material") }}</option>
              <option value="fitting">{{ t("materials.category.fitting") }}</option>
              <option value="hardware">{{ t("materials.category.hardware") }}</option>
              <option value="consumable">{{ t("materials.category.consumable") }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.dimensionType") }}</label>
            <select v-model="form.dimension_type" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="length">{{ t("materials.dimensionType.length") }}</option>
              <option value="area">{{ t("materials.dimensionType.area") }}</option>
              <option value="count">{{ t("materials.dimensionType.count") }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.pieceType") }}</label>
            <input v-model="form.piece_type" list="piece-types" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <datalist id="piece-types"><option v-for="p in PIECE_TYPE_SUGGESTIONS" :key="p" :value="p" /></datalist>
          </div>

          <template v-if="isMetalCategory">
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.metalType") }}</label>
              <select v-model="form.metal_type" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
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
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.steelGrade") }}</label>
              <input v-model="form.steel_grade" list="steel-grades" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <datalist id="steel-grades"><option v-for="g in STEEL_GRADE_SUGGESTIONS" :key="g" :value="g" /></datalist>
            </div>
          </template>

          <template v-if="isWoodCategory">
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.woodSpecies") }}</label>
              <input v-model="form.wood_species" list="wood-species" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <datalist id="wood-species"><option v-for="s in WOOD_SPECIES_SUGGESTIONS" :key="s" :value="s" /></datalist>
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.woodGrade") }}</label>
              <input v-model="form.wood_grade" list="wood-grades" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <datalist id="wood-grades"><option v-for="g in WOOD_GRADE_SUGGESTIONS" :key="g" :value="g" /></datalist>
            </div>
          </template>

          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.length") }}</label>
            <input v-model.number="form.standard_length_mm" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div v-if="form.dimension_type !== 'length'">
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.width") }}</label>
            <input v-model.number="form.standard_width_mm" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.thickness") }}</label>
            <input v-model.number="form.standard_thickness_mm" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>

          <div v-if="form.dimension_type === 'length'">
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.sawBlade") }}</label>
            <select v-model="form.saw_blade_id" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" @change="onSawBladeChange">
              <option :value="null">{{ t("materials.sawBlade.none") }}</option>
              <option v-for="b in store.sawBlades" :key="b.id" :value="b.id">{{ b.name }} ({{ b.kerf_mm }}mm)</option>
            </select>
          </div>
          <div v-if="form.dimension_type === 'length'">
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.kerf") }}</label>
            <input v-model.number="form.kerf_mm" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>

          <div v-if="!editingId">
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.initialStock") }}</label>
            <input v-model.number="form.quantity_in_stock" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.lowStockThreshold") }}</label>
            <input v-model.number="form.low_stock_threshold" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("materials.unitCost", { unit: unitFor(form.dimension_type) }) }}</label>
            <input v-model.number="form.unit_cost" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <p class="text-xs text-slate-500 mt-1">{{ t("materials.unitCost.hint") }}</p>
          </div>
        </div>
        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex gap-2">
          <button type="submit" class="bg-accent-600 hover:bg-accent-700 text-white text-sm font-medium rounded-lg px-4 py-2">
            {{ editingId ? t("common.saveChanges") : t("common.add") }}
          </button>
          <button v-if="editingId" type="button" class="text-sm text-slate-500 px-4 py-2" @click="cancelEdit">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>

    <div class="space-y-3">
      <div v-for="m in store.materials" :key="m.id" class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-slate-900">{{ m.name }}</span>
            <span v-if="m.is_mock" class="ml-2 text-xs text-slate-500 bg-slate-100 rounded px-1.5 py-0.5">{{ t("common.demo") }}</span>
            <span class="ml-2 text-xs text-slate-500">{{ t(`materials.category.${m.category}`) }} &middot; {{ t(`materials.dimensionType.${m.dimension_type}`) }}</span>
          </div>
          <div class="flex gap-3">
            <button class="text-sm text-accent-600" @click="startEdit(m)">{{ t("common.edit") }}</button>
            <button class="text-sm text-red-600" @click="removeMaterial(m.id, m.name)">{{ t("common.delete") }}</button>
          </div>
        </div>

        <div class="mt-1 text-xs text-slate-500">
          <span v-if="m.steel_grade">{{ m.steel_grade }}</span>
          <span v-if="m.wood_species">{{ m.wood_species }}<span v-if="m.wood_grade"> &middot; {{ m.wood_grade }}</span></span>
          <span v-if="m.piece_type"> &middot; {{ m.piece_type }}</span>
          <span v-if="m.standard_length_mm"> &middot; {{ m.standard_length_mm }} &times; {{ m.standard_width_mm ?? "–" }} &times; {{ m.standard_thickness_mm ?? "–" }} mm</span>
          <span v-if="m.saw_blade_name"> &middot; {{ m.saw_blade_name }}</span>
        </div>

        <div class="mt-2 flex items-center gap-4 text-sm">
          <span :class="m.quantity_in_stock <= m.low_stock_threshold ? 'text-red-600 font-medium' : 'text-slate-600'">
            {{ t("materials.stock") }}: {{ m.quantity_in_stock }} {{ unitFor(m.dimension_type) }}
          </span>
          <span class="text-slate-500">{{ t("materials.lowStockBelow", { n: m.low_stock_threshold }) }}</span>
          <span class="text-slate-500">{{ t("materials.landedCost") }}: {{ m.unit_cost }} €/{{ unitFor(m.dimension_type) }}</span>
        </div>
        <div class="mt-3 flex items-center gap-2 flex-wrap">
          <button class="text-sm text-accent-600" @click="openRestock(m.id)">{{ t("materials.restock") }}</button>
          <button v-if="m.dimension_type !== 'count'" class="text-sm text-slate-600" @click="openYieldCalc(m.id)">{{ t("materials.yieldCalculator") }}</button>
          <button v-if="m.dimension_type === 'length'" class="text-sm text-slate-600" @click="openOptimizer(m.id)">{{ t("materials.cuttingOptimizer") }}</button>
        </div>

        <div v-if="restockOpenFor === m.id" class="mt-3 border-t border-slate-100 pt-3">
          <p class="text-xs text-slate-500 mb-2">{{ t("materials.restock.hint") }}</p>
          <div class="flex items-end gap-2 flex-wrap">
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.restock.quantity", { unit: unitFor(m.dimension_type) }) }}</label>
              <input v-model.number="restockForm.quantity_delta" type="number" step="any" class="w-36 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.restock.purchasePrice") }}</label>
              <input v-model.number="restockForm.purchase_price" type="number" step="any" min="0" class="w-32 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.restock.shippingCost") }}</label>
              <input v-model.number="restockForm.shipping_cost" type="number" step="any" min="0" class="w-32 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <button class="text-sm bg-slate-800 text-white rounded-lg px-3 py-1.5" @click="submitRestock(m.id)">{{ t("materials.restock.confirm") }}</button>
          </div>
          <p v-if="restockError" class="text-sm text-red-600 mt-2">{{ restockError }}</p>
        </div>

        <div v-if="yieldForm.materialId === m.id" class="mt-3 border-t border-slate-100 pt-3">
          <div class="flex items-end gap-2 flex-wrap">
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.blankLength") }}</label>
              <input v-model.number="yieldForm.blank_length_mm" type="number" step="any" class="w-40 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <div v-if="m.dimension_type === 'area'">
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.blankWidth") }}</label>
              <input v-model.number="yieldForm.blank_width_mm" type="number" step="any" class="w-40 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">{{ t("materials.quantityNeeded") }}</label>
              <input v-model.number="yieldForm.quantity_needed" type="number" min="1" class="w-32 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <button class="text-sm bg-slate-800 text-white rounded-lg px-3 py-1.5" @click="runYieldCalc">{{ t("materials.calculate") }}</button>
          </div>
          <p v-if="yieldError" class="text-sm text-red-600 mt-2">{{ yieldError }}</p>
          <div v-if="yieldResult" class="mt-3">
            <div class="text-sm text-slate-700 grid grid-cols-2 gap-x-6 gap-y-1 mb-3">
              <span>{{ t("materials.piecesPerStockUnit") }}: <strong>{{ yieldResult.pieces_per_stock_unit }}</strong></span>
              <span>{{ t("materials.stockUnitsNeeded") }}: <strong>{{ yieldResult.stock_units_needed }}</strong></span>
              <span>{{ t("materials.wastePerStockUnit") }}: <strong>{{ yieldResult.waste_per_stock_unit }} {{ yieldResult.unit }}</strong></span>
              <span>{{ t("materials.wastePercentage") }}: <strong>{{ yieldResult.waste_percentage }}%</strong></span>
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
                <span class="text-slate-500">{{ c.piece_count }} {{ t("materials.optimizer.pieces") }}, {{ c.total_length_mm }}mm</span>
              </li>
            </ul>
            <button class="text-sm bg-slate-800 text-white rounded-lg px-3 py-1.5" @click="runOptimizer(m.id)">{{ t("materials.optimizer.run") }}</button>
          </template>

          <p v-if="cutError" class="text-sm text-red-600 mt-2">{{ cutError }}</p>
          <div v-if="cutPlan && cutPlan.material_id === m.id" class="mt-3">
            <div class="text-sm text-slate-700 grid grid-cols-3 gap-x-6 gap-y-1 mb-3">
              <span>{{ t("materials.optimizer.barsNeeded") }}: <strong>{{ cutPlan.bars_needed }}</strong></span>
              <span>{{ t("materials.optimizer.totalPieces") }}: <strong>{{ cutPlan.total_pieces }}</strong></span>
              <span>{{ t("materials.optimizer.totalWaste") }}: <strong>{{ cutPlan.total_waste_mm }}mm ({{ cutPlan.waste_percentage }}%)</strong></span>
            </div>
            <CuttingBarsVisual :stock-length="cutPlan.stock_length_mm" :kerf="cutPlan.kerf_mm" :bars="cutBarsForVisual" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
