<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { KnifeModel, KnifeModelMaterial, KnifeModelTreatment, KnifeType, MaterialRole } from "@/types";

const { t, money } = useI18n();
const store = useAppStore();
const route = useRoute();
const router = useRouter();

onMounted(async () => {
  await Promise.all([store.fetchKnifeModels(), store.fetchMaterials(), store.fetchTreatmentRecipes()]);
  const editId = Number(route.query.edit);
  if (editId) {
    const target = store.knifeModels.find((m) => m.id === editId);
    if (target) startEdit(target);
    router.replace({ query: {} });
  }
});

const emptyForm = () => ({
  name: "",
  knife_type: "fixed" as KnifeType,
  base_labor_hours: 0,
  sale_price: 0,
  margin_percent_override: null as number | null,
  materials: [] as KnifeModelMaterial[],
  treatments: [] as KnifeModelTreatment[],
});

const form = reactive(emptyForm());
const formError = ref("");
const editingId = ref<number | null>(null);

function addMaterialLine() {
  form.materials.push({ material_id: store.materials[0]?.id ?? 0, role: "other" as MaterialRole, blank_length_mm: null, blank_width_mm: null, blank_thickness_mm: null, quantity: 1 });
}
function removeMaterialLine(i: number) {
  form.materials.splice(i, 1);
}
function addTreatmentLine() {
  form.treatments.push({ treatment_recipe_id: store.treatmentRecipes[0]?.id ?? 0, step_order: form.treatments.length + 1 });
}
function removeTreatmentLine(i: number) {
  form.treatments.splice(i, 1);
}

function dimensionTypeOf(materialId: number) {
  return store.materials.find((m) => m.id === materialId)?.dimension_type;
}

function startEdit(km: KnifeModel) {
  editingId.value = km.id;
  Object.assign(form, {
    name: km.name,
    knife_type: km.knife_type,
    base_labor_hours: km.base_labor_hours,
    sale_price: km.sale_price,
    margin_percent_override: km.margin_percent_override,
    materials: km.materials.map((m) => ({ ...m })),
    treatments: km.treatments.map((tr) => ({ ...tr })),
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function cancelEdit() {
  editingId.value = null;
  Object.assign(form, emptyForm());
}

async function submit() {
  formError.value = "";
  // v-model.number leaves an emptied number input as "" rather than
  // null, which the API rejects for an optional float field.
  const payload = { ...form, margin_percent_override: form.margin_percent_override === ("" as unknown) ? null : form.margin_percent_override };
  try {
    if (editingId.value) {
      await store.updateKnifeModel(editingId.value, payload);
      cancelEdit();
    } else {
      await store.createKnifeModel(payload);
      Object.assign(form, emptyForm());
    }
  } catch (err) {
    formError.value = err instanceof ApiError ? err.message : t("common.error");
  }
}

const deleteError = ref("");

async function remove(id: number, name: string) {
  if (!confirm(t("common.confirmDeleteNamed", { name }))) return;
  deleteError.value = "";
  try {
    await store.deleteKnifeModel(id);
  } catch (err) {
    deleteError.value = err instanceof ApiError ? err.message : t("common.deleteFailed");
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-6">{{ t("knifeModels.title") }}</h1>
    <p v-if="deleteError" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ deleteError }}</p>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-8">
      <h2 class="font-semibold text-slate-900 mb-3">{{ editingId ? t("knifeModels.editTitle") : t("knifeModels.addTitle") }}</h2>
      <form class="space-y-4" @submit.prevent="submit">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="col-span-2 md:col-span-4">
            <label class="block text-xs text-slate-500 mb-1">{{ t("knifeModels.name") }}</label>
            <input v-model="form.name" required class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("knifeModels.knifeType") }}</label>
            <select v-model="form.knife_type" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="fixed">{{ t("knifeModels.knifeType.fixed") }}</option>
              <option value="folder">{{ t("knifeModels.knifeType.folder") }}</option>
              <option value="kitchen">{{ t("knifeModels.knifeType.kitchen") }}</option>
              <option value="table">{{ t("knifeModels.knifeType.table") }}</option>
              <option value="japanese">{{ t("knifeModels.knifeType.japanese") }}</option>
              <option value="other">{{ t("knifeModels.knifeType.other") }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("knifeModels.laborHours") }}</label>
            <input v-model.number="form.base_labor_hours" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("knifeModels.salePrice") }}</label>
            <input v-model.number="form.sale_price" type="number" step="any" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">{{ t("knifeModels.marginOverride") }}</label>
            <input v-model.number="form.margin_percent_override" type="number" step="any" min="0" max="99" :placeholder="t('knifeModels.marginOverride.placeholder')" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-slate-700">{{ t("knifeModels.materialsRequired") }}</span>
            <button type="button" class="text-sm text-accent-600" @click="addMaterialLine">{{ t("knifeModels.addMaterial") }}</button>
          </div>
          <div v-for="(line, i) in form.materials" :key="i" class="grid grid-cols-12 gap-2 mb-2 items-center">
            <select v-model.number="line.material_id" class="col-span-4 rounded-lg border border-slate-300 px-2 py-1 text-sm">
              <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
            </select>
            <select v-model="line.role" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm">
              <option value="blade">{{ t("knifeModels.role.blade") }}</option>
              <option value="handle">{{ t("knifeModels.role.handle") }}</option>
              <option value="fitting">{{ t("knifeModels.role.fitting") }}</option>
              <option value="hardware">{{ t("knifeModels.role.hardware") }}</option>
              <option value="other">{{ t("knifeModels.role.other") }}</option>
            </select>
            <input v-if="dimensionTypeOf(line.material_id) !== 'count'" v-model.number="line.blank_length_mm" type="number" step="any" :placeholder="t('materials.blankLength')" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-if="dimensionTypeOf(line.material_id) === 'area'" v-model.number="line.blank_width_mm" type="number" step="any" :placeholder="t('materials.blankWidth')" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-if="dimensionTypeOf(line.material_id) !== 'count'" v-model.number="line.blank_thickness_mm" type="number" step="any" :placeholder="t('materials.thickness')" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-if="dimensionTypeOf(line.material_id) === 'count'" v-model.number="line.quantity" type="number" step="any" placeholder="Qty" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <button type="button" class="col-span-1 text-red-600 text-sm" @click="removeMaterialLine(i)">✕</button>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-slate-700">{{ t("knifeModels.pipeline") }}</span>
            <button type="button" class="text-sm text-accent-600" @click="addTreatmentLine">{{ t("knifeModels.addStep") }}</button>
          </div>
          <div v-for="(line, i) in form.treatments" :key="i" class="grid grid-cols-12 gap-2 mb-2 items-center">
            <input v-model.number="line.step_order" type="number" class="col-span-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <select v-model.number="line.treatment_recipe_id" class="col-span-9 rounded-lg border border-slate-300 px-2 py-1 text-sm">
              <option v-for="r in store.treatmentRecipes" :key="r.id" :value="r.id">{{ r.name }}</option>
            </select>
            <button type="button" class="col-span-1 text-red-600 text-sm" @click="removeTreatmentLine(i)">✕</button>
          </div>
        </div>

        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex gap-2">
          <button type="submit" class="bg-accent-600 hover:bg-accent-700 text-white text-sm font-medium rounded-lg px-4 py-2">
            {{ editingId ? t("common.saveChanges") : t("common.save") }}
          </button>
          <button v-if="editingId" type="button" class="text-sm text-slate-500 px-4 py-2" @click="cancelEdit">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>

    <div class="space-y-3">
      <div v-for="km in store.knifeModels" :key="km.id" class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="flex items-center justify-between">
          <div>
            <router-link :to="`/knife-models/${km.id}`" class="font-medium text-slate-900 hover:text-accent-600">{{ km.name }}</router-link>
            <span class="ml-2 text-xs text-slate-500 bg-accent-50 text-accent-700 rounded px-1.5 py-0.5">{{ t(`knifeModels.knifeType.${km.knife_type}`) }}</span>
            <span v-if="km.is_mock" class="ml-2 text-xs text-slate-500 bg-slate-100 rounded px-1.5 py-0.5">{{ t("common.demo") }}</span>
          </div>
          <div class="flex gap-3">
            <button class="text-sm text-accent-600" @click="startEdit(km)">{{ t("common.edit") }}</button>
            <button class="text-sm text-red-600" @click="remove(km.id, km.name)">{{ t("common.delete") }}</button>
          </div>
        </div>
        <p class="text-sm text-slate-500 mt-1">{{ t("knifeModels.buildTime") }}: {{ t("knifeModels.hours", { n: km.base_labor_hours }) }} &middot; {{ money(km.sale_price) }}</p>
        <p class="text-sm text-slate-600 mt-2">
          {{ t("knifeModels.materials") }}: {{ km.materials.map((m) => m.material_name).join(", ") || t("knifeModels.none") }}
        </p>
        <p class="text-sm text-slate-600">
          {{ t("knifeModels.process") }}: {{ km.treatments.map((tr) => tr.treatment_recipe_name).join(" → ") || t("knifeModels.none") }}
        </p>
      </div>
    </div>
  </div>
</template>
