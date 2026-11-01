<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { TreatmentRecipe, TreatmentStep, TreatmentType } from "@/types";

const { t } = useI18n();
const store = useAppStore();
onMounted(() => store.fetchTreatmentRecipes());

const TREATMENT_TYPES: TreatmentType[] = ["heat_treatment", "damascus_etch", "bluing", "browning", "acid_patina", "other"];

const emptyForm = () => ({
  name: "",
  treatment_type: "heat_treatment" as TreatmentType,
  applies_to: "",
  notes: "",
  steps: [] as TreatmentStep[],
});

const form = reactive(emptyForm());
const formError = ref("");
const editingId = ref<number | null>(null);

function addStep() {
  form.steps.push({ step_order: form.steps.length + 1, description: "", temperature_c: null, duration_minutes: null, medium: null });
}
function removeStep(index: number) {
  form.steps.splice(index, 1);
}

function startEdit(r: TreatmentRecipe) {
  editingId.value = r.id;
  Object.assign(form, {
    name: r.name,
    treatment_type: r.treatment_type,
    applies_to: r.applies_to,
    notes: r.notes ?? "",
    steps: r.steps.map((s) => ({ ...s })),
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
      await store.updateTreatmentRecipe(editingId.value, form);
      cancelEdit();
    } else {
      await store.createTreatmentRecipe(form);
      Object.assign(form, emptyForm());
    }
  } catch (err) {
    formError.value = err instanceof ApiError ? err.message : "Failed";
  }
}

async function remove(id: number) {
  try {
    await store.deleteTreatmentRecipe(id);
  } catch (err) {
    alert(err instanceof ApiError ? err.message : "Failed to delete recipe");
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-1">{{ t("treatments.title") }}</h1>
    <p class="text-sm text-slate-500 mb-6">{{ t("treatments.subtitle") }}</p>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-8">
      <h2 class="font-semibold text-slate-900 mb-3">{{ editingId ? t("treatments.editTitle") : t("treatments.addTitle") }}</h2>
      <form class="space-y-3" @submit.prevent="submit">
        <div class="grid grid-cols-2 gap-3">
          <input v-model="form.name" :placeholder="t('treatments.name')" required class="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select v-model="form.treatment_type" class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option v-for="type in TREATMENT_TYPES" :key="type" :value="type">{{ t(`treatments.type.${type}`) }}</option>
          </select>
          <input v-model="form.applies_to" :placeholder="t('treatments.appliesTo')" required class="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <textarea v-model="form.notes" :placeholder="t('common.notes')" class="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm" rows="2"></textarea>
        </div>

        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-slate-700">{{ t("treatments.steps") }}</span>
            <button type="button" class="text-sm text-indigo-600" @click="addStep">{{ t("treatments.addStep") }}</button>
          </div>
          <div v-for="(step, i) in form.steps" :key="i" class="grid grid-cols-12 gap-2 mb-2 items-center">
            <input v-model.number="step.step_order" type="number" class="col-span-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-model="step.description" placeholder="Description" required class="col-span-5 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-model.number="step.temperature_c" type="number" step="any" placeholder="°C" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-model.number="step.duration_minutes" type="number" step="any" placeholder="min" class="col-span-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <input v-model="step.medium" placeholder="Medium" class="col-span-2 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <button type="button" class="col-span-1 text-red-600 text-sm" @click="removeStep(i)">✕</button>
          </div>
        </div>

        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <div class="flex gap-2">
          <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2">
            {{ editingId ? t("common.saveChanges") : t("treatments.saveRecipe") }}
          </button>
          <button v-if="editingId" type="button" class="text-sm text-slate-500 px-4 py-2" @click="cancelEdit">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>

    <div class="space-y-3">
      <div v-for="r in store.treatmentRecipes" :key="r.id" class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-slate-900">{{ r.name }}</span>
            <span v-if="r.is_mock" class="ml-2 text-xs text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">{{ t("common.demo") }}</span>
            <span class="ml-2 text-xs text-slate-500 bg-indigo-50 text-indigo-700 rounded px-1.5 py-0.5">{{ t(`treatments.type.${r.treatment_type}`) }}</span>
          </div>
          <div class="flex gap-3">
            <button class="text-sm text-indigo-600" @click="startEdit(r)">{{ t("common.edit") }}</button>
            <button class="text-sm text-red-600" @click="remove(r.id)">{{ t("common.delete") }}</button>
          </div>
        </div>
        <p class="text-sm text-slate-500 mt-1">{{ r.applies_to }}</p>
        <ol class="mt-2 space-y-1 text-sm text-slate-700 list-decimal list-inside">
          <li v-for="s in r.steps" :key="s.id">
            {{ s.description }}
            <span class="text-slate-400">
              <template v-if="s.temperature_c !== null">— {{ s.temperature_c }}°C</template>
              <template v-if="s.duration_minutes !== null">, {{ s.duration_minutes }} min</template>
              <template v-if="s.medium">, {{ s.medium }}</template>
            </span>
          </li>
        </ol>
      </div>
    </div>
  </div>
</template>
