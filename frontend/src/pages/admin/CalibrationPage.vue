<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { saveBlob } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { CalibrationFeature, CalibrationResult } from "@/types";

const { t } = useI18n();
const store = useAppStore();
const router = useRouter();

const EXPORT_KERF_KEY = "knifeforge_export_kerf"; // shared with the editor's export menu

function storedKerf(): number {
  try {
    const v = Number(localStorage.getItem(EXPORT_KERF_KEY));
    return Number.isFinite(v) && v >= 0 && v <= 3 ? v : 0;
  } catch {
    return 0;
  }
}

const features = ref<CalibrationFeature[]>([]);
const setup = reactive({ kerf: storedKerf(), machine: "", material: "" });
const readings = reactive<Record<string, number | "">>({});
const result = ref<CalibrationResult | null>(null);
const error = ref("");
const busy = ref(false);
const applied = ref(false);

onMounted(async () => {
  features.value = await store.fetchCalibrationFeatures();
  for (const f of features.value) readings[f.key] = "";
});

const filled = computed(() =>
  Object.fromEntries(Object.entries(readings).filter(([, v]) => v !== "" && Number.isFinite(Number(v))).map(([k, v]) => [k, Number(v)])),
);

const mm = (v: number, digits = 2) => v.toFixed(digits).replace(".", ",");
const signed = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "") + mm(Math.abs(v));

async function createPlate() {
  error.value = "";
  try {
    const tpl = (await store.fetchDesignTemplates()).find((x) => x.key === "calibration-plate");
    if (!tpl) return;
    const created = await store.createDesign({ name: t("calibration.plateName"), kind: "template", document: tpl.document });
    router.push(`/designs/${created.id}`);
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

async function downloadSheet() {
  error.value = "";
  try {
    saveBlob(await store.downloadCalibrationSheet(Number(setup.kerf) || 0, setup.machine.trim(), setup.material.trim()), "planche-de-controle-releve.pdf");
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

async function analyse() {
  error.value = "";
  applied.value = false;
  busy.value = true;
  try {
    result.value = await store.analyseCalibration(Math.max(0, Math.min(3, Number(setup.kerf) || 0)), filled.value);
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

function applySuggested() {
  if (result.value?.suggested_kerf_mm == null) return;
  try {
    localStorage.setItem(EXPORT_KERF_KEY, String(result.value.suggested_kerf_mm));
    applied.value = true;
  } catch {
    error.value = t("calibration.storageBlocked");
  }
}

function clearReadings() {
  for (const k of Object.keys(readings)) readings[k] = "";
  result.value = null;
}
</script>

<template>
  <div class="page max-w-7xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("calibration.title") }}</h1>
        <p class="page-lead">{{ t("calibration.lead") }}</p>
      </div>
    </header>

    <p v-if="error" class="mb-4 text-sm text-red-700" role="alert">{{ error }}</p>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] items-start">
      <div class="space-y-4 min-w-0">
        <section class="sheet p-4 space-y-3">
          <h2 class="sheet-title">{{ t("calibration.step1") }}</h2>
          <p class="text-sm text-slate-600">{{ t("calibration.step1Text") }}</p>
          <button class="btn btn-primary" @click="createPlate">{{ t("calibration.createPlate") }}</button>
        </section>

        <section class="sheet p-4 space-y-3">
          <h2 class="sheet-title">{{ t("calibration.step2") }}</h2>
          <p class="text-sm text-slate-600">{{ t("calibration.step2Text") }}</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block">
              <span class="field-label">{{ t("calibration.machine") }}</span>
              <input v-model="setup.machine" class="input w-full" maxlength="80" :placeholder="t('calibration.machineHint')" />
            </label>
            <label class="block">
              <span class="field-label">{{ t("calibration.material") }}</span>
              <input v-model="setup.material" class="input w-full" maxlength="80" :placeholder="t('calibration.materialHint')" />
            </label>
            <label class="block sm:col-span-2">
              <span class="field-label">{{ t("calibration.kerfUsed") }}</span>
              <input v-model.number="setup.kerf" type="number" min="0" max="3" step="0.01" class="input w-32 text-right" />
              <span class="block mt-1 text-xs text-slate-500">{{ t("calibration.kerfUsedHint") }}</span>
            </label>
          </div>
          <button class="btn btn-outline" @click="downloadSheet">{{ t("calibration.sheet") }}</button>
        </section>
      </div>

      <div class="space-y-4 min-w-0">
        <section class="sheet p-4">
          <h2 class="sheet-title mb-1">{{ t("calibration.step3") }}</h2>
          <p class="text-sm text-slate-600 mb-3">{{ t("calibration.step3Text") }}</p>
          <form @submit.prevent="analyse">
            <div class="-mx-1 overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-slate-500">
                    <th class="font-normal pb-1 w-8"></th>
                    <th class="font-normal pb-1">{{ t("calibration.dimension") }}</th>
                    <th class="font-normal pb-1 text-right">{{ t("calibration.nominal") }}</th>
                    <th class="font-normal pb-1 text-right">{{ t("calibration.measured") }}</th>
                    <th class="font-normal pb-1 text-right">{{ t("calibration.error") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="f in features" :key="f.key" class="border-t border-slate-100">
                    <td class="py-1.5 font-semibold text-accent-700">{{ f.key }}</td>
                    <td class="py-1.5">
                      <span class="block">{{ f.label }}</span>
                      <span class="block text-xs text-slate-500">{{ t(`calibration.kind.${f.kind}`) }} · {{ f.how }}</span>
                    </td>
                    <td class="py-1.5 text-right tabular-nums">{{ mm(f.nominal_mm) }}</td>
                    <td class="py-1.5 text-right">
                      <input
                        v-model.number="readings[f.key]"
                        type="number"
                        step="0.01"
                        min="0"
                        class="input-sm w-24 text-right tabular-nums"
                        :aria-label="`${f.key} — ${f.label} (mm)`"
                      />
                    </td>
                    <td class="py-1.5 text-right tabular-nums">
                      <template v-for="r in result?.features.filter((x) => x.key === f.key)" :key="r.key">
                        <span class="tag font-medium" :class="r.within_tolerance ? 'tag-success' : 'tag-danger'">{{ signed(r.error_mm) }}</span>
                      </template>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button type="submit" class="btn btn-primary" :disabled="busy || Object.keys(filled).length === 0">{{ t("calibration.analyse") }}</button>
              <button type="button" class="btn btn-outline" @click="clearReadings">{{ t("calibration.clear") }}</button>
            </div>
          </form>
        </section>

        <section v-if="result" class="sheet p-4 space-y-3" aria-live="polite">
          <h2 class="sheet-title">{{ t("calibration.result") }}</h2>
          <p class="text-sm font-medium" :class="result.within_tolerance ? 'text-emerald-700' : 'text-amber-700'">
            {{ result.within_tolerance ? t("calibration.verdictOk", { max: mm(result.max_error_mm) }) : t("calibration.verdictOff", { max: mm(result.max_error_mm) }) }}
          </p>
          <dl class="grid gap-x-6 gap-y-2 sm:grid-cols-2 text-sm">
            <div v-if="result.kerf_estimate_mm != null">
              <dt class="text-slate-500">{{ t("calibration.kerfReal") }}</dt>
              <dd class="font-medium tabular-nums">{{ mm(result.kerf_estimate_mm) }} mm
                <span class="text-slate-500 font-normal">{{ t("calibration.spread", { s: mm(result.kerf_spread_mm ?? 0) }) }}</span>
              </dd>
            </div>
            <div v-if="result.suggested_kerf_mm != null">
              <dt class="text-slate-500">{{ t("calibration.suggested") }}</dt>
              <dd class="font-medium tabular-nums">{{ mm(result.suggested_kerf_mm) }} mm
                <span v-if="result.residual_mm != null" class="text-slate-500 font-normal">{{ t("calibration.residual", { r: mm(result.residual_mm) }) }}</span>
              </dd>
            </div>
            <div v-if="result.scale_error_ppm != null">
              <dt class="text-slate-500">{{ t("calibration.scale") }}</dt>
              <dd class="font-medium tabular-nums">{{ t("calibration.scaleValue", { mm: mm((result.scale_error_ppm * 1000) / 1e6, 2) }) }}</dd>
            </div>
          </dl>
          <ul class="text-sm text-slate-700 list-disc pl-5 space-y-1">
            <li v-for="a in result.advice" :key="a">{{ t(`calibration.advice.${a}`) }}</li>
          </ul>
          <div v-if="result.suggested_kerf_mm != null && !result.within_tolerance" class="flex flex-wrap items-center gap-3">
            <button class="btn btn-primary" @click="applySuggested">{{ t("calibration.apply", { k: mm(result.suggested_kerf_mm) }) }}</button>
            <span v-if="applied" class="text-sm text-emerald-700">{{ t("calibration.applied") }}</span>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
