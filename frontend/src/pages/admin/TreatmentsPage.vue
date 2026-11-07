<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import EditorIcon from "@/components/EditorIcon.vue";
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

const showForm = ref(false);

function startEdit(r: TreatmentRecipe) {
  showForm.value = true;
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
  showForm.value = false;
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
      showForm.value = false;
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
    await store.deleteTreatmentRecipe(id);
  } catch (err) {
    deleteError.value = err instanceof ApiError ? err.message : t("common.deleteFailed");
  }
}
</script>

<template>
  <div class="page max-w-4xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("treatments.title") }}</h1>
        <p class="page-lead">{{ t("treatments.subtitle") }}</p>
      </div>
      <button v-if="!showForm" class="btn btn-primary" @click="showForm = true">+ {{ t("treatments.addTitle") }}</button>
    </header>
    <p v-if="deleteError" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ deleteError }}</p>

    <div v-if="showForm || editingId" class="sheet p-5 mb-8">
      <h2 class="sheet-title mb-4">{{ editingId ? t("treatments.editTitle") : t("treatments.addTitle") }}</h2>
      <form class="space-y-3" @submit.prevent="submit">
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="field-label">{{ t("treatments.name") }}</span>
            <input v-model="form.name" required class="input w-full" />
          </label>
          <label class="block"><span class="field-label">{{ t("treatments.typeLabel") }}</span>
            <select v-model="form.treatment_type" class="input w-full">
              <option v-for="type in TREATMENT_TYPES" :key="type" :value="type">{{ t(`treatments.type.${type}`) }}</option>
            </select>
          </label>
          <label class="block col-span-2"><span class="field-label">{{ t("treatments.appliesTo") }}</span>
            <input v-model="form.applies_to" required class="input w-full" />
          </label>
          <label class="block col-span-2"><span class="field-label">{{ t("common.notes") }}</span>
            <textarea v-model="form.notes" class="input w-full" rows="2"></textarea>
          </label>
        </div>

        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-slate-700">{{ t("treatments.steps") }}</span>
            <button type="button" class="link-action" @click="addStep">{{ t("treatments.addStep") }}</button>
          </div>
          <div v-for="(step, i) in form.steps" :key="i" class="grid grid-cols-12 gap-2 mb-2 items-center">
            <input v-model.number="step.step_order" type="number" aria-label="#" class="col-span-1 input-sm" />
            <input v-model="step.description" :placeholder="t('treatments.step.description')" :aria-label="t('treatments.step.description')" required class="col-span-5 input-sm" />
            <input v-model.number="step.temperature_c" type="number" step="any" placeholder="°C" aria-label="°C" class="col-span-2 input-sm" />
            <input v-model.number="step.duration_minutes" type="number" step="any" placeholder="min" aria-label="min" class="col-span-1 input-sm" />
            <input v-model="step.medium" :placeholder="t('treatments.step.medium')" :aria-label="t('treatments.step.medium')" class="col-span-2 input-sm" />
            <button type="button" class="col-span-1 justify-self-center p-1 rounded text-slate-500 hover:text-red-700 hover:bg-slate-100" :aria-label="t('common.delete')" @click="removeStep(i)"><EditorIcon name="close" :size="14" /></button>
          </div>
        </div>

        <p v-if="formError" role="alert" class="text-sm text-red-700">{{ formError }}</p>
        <div class="flex gap-2">
          <button type="submit" class="btn btn-primary">
            {{ editingId ? t("common.saveChanges") : t("treatments.saveRecipe") }}
          </button>
          <button type="button" class="btn btn-outline" @click="cancelEdit">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>

    <div class="space-y-3">
      <div v-for="r in store.treatmentRecipes" :key="r.id" class="sheet p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-semibold text-slate-900">{{ r.name }}</span>
            <span class="tag tag-accent">{{ t(`treatments.type.${r.treatment_type}`) }}</span>
            <span v-if="r.is_mock" class="tag tag-neutral">{{ t("common.demo") }}</span>
          </div>
          <div class="flex gap-3">
            <button class="link-action" @click="startEdit(r)">{{ t("common.edit") }}</button>
            <button class="link-danger" @click="remove(r.id, r.name)">{{ t("common.delete") }}</button>
          </div>
        </div>
        <p class="text-sm text-slate-500 mt-1">{{ r.applies_to }}</p>
        <ol class="mt-2 space-y-1 text-sm text-slate-700 list-decimal list-inside">
          <li v-for="s in r.steps" :key="s.id">
            {{ s.description }}
            <span class="text-slate-500">— {{ [s.temperature_c !== null ? `${s.temperature_c} °C` : "", s.duration_minutes !== null ? `${s.duration_minutes} min` : "", s.medium ?? ""].filter(Boolean).join(" · ") }}</span>
          </li>
        </ol>
      </div>
    </div>
  </div>
</template>
