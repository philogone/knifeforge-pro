<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { CostBreakdown } from "@/types";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const store = useAppStore();
const modelId = Number(route.params.id);

onMounted(async () => {
  await Promise.all([store.fetchKnifeModels(), store.fetchTreatmentRecipes()]);
  cost.value = await store.fetchCostBreakdown(modelId);
});

const model = computed(() => store.knifeModels.find((m) => m.id === modelId));
const recipesByModel = computed(() =>
  (model.value?.treatments ?? [])
    .slice()
    .sort((a, b) => a.step_order - b.step_order)
    .map((t) => store.treatmentRecipes.find((r) => r.id === t.treatment_recipe_id))
    .filter((r) => r !== undefined),
);

const cost = ref<CostBreakdown | null>(null);
const priceDelta = computed(() => {
  if (!cost.value) return null;
  return cost.value.current_sale_price - cost.value.suggested_sale_price;
});

function editModel() {
  router.push({ path: "/knife-models", query: { edit: String(modelId) } });
}

async function deleteModel() {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await store.deleteKnifeModel(modelId);
    router.push("/knife-models");
  } catch (err) {
    alert(err instanceof ApiError ? String(err.detail) : "Failed to delete knife model");
  }
}
</script>

<template>
  <div v-if="model" class="max-w-3xl mx-auto px-4 py-8">
    <router-link to="/knife-models" class="text-sm text-slate-400">&larr; {{ t("common.backToList") }}</router-link>
    <div class="flex items-center justify-between mt-1">
      <div class="flex items-center gap-2">
        <h1 class="text-2xl font-bold text-slate-900">{{ model.name }}</h1>
        <span class="text-xs text-slate-500 bg-indigo-50 text-indigo-700 rounded px-1.5 py-0.5">{{ t(`knifeModels.knifeType.${model.knife_type}`) }}</span>
      </div>
      <div class="flex gap-3">
        <button class="text-sm text-indigo-600" @click="editModel">{{ t("common.edit") }}</button>
        <button class="text-sm text-red-600" @click="deleteModel">{{ t("common.delete") }}</button>
      </div>
    </div>
    <p class="text-sm text-slate-500 mt-1">{{ t("knifeModels.buildTime") }}: {{ t("knifeModels.hours", { n: model.base_labor_hours }) }} &middot; ${{ model.sale_price }}</p>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mt-6">
      <h2 class="font-semibold text-slate-900 mb-2">{{ t("knifeModels.materialsRequired") }}</h2>
      <table class="w-full text-sm">
        <tbody>
          <tr v-for="m in model.materials" :key="m.id" class="border-t border-slate-100 first:border-0">
            <td class="py-2 font-medium text-slate-800">{{ m.material_name }}</td>
            <td class="py-2 text-slate-500">{{ t(`knifeModels.role.${m.role}`) }}</td>
            <td class="py-2 text-slate-500">
              <span v-if="m.blank_length_mm">{{ m.blank_length_mm }} &times; {{ m.blank_width_mm ?? "–" }} &times; {{ m.blank_thickness_mm ?? "–" }} mm</span>
              <span v-else>{{ m.quantity }} unit(s)</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="cost" class="bg-white rounded-xl border border-slate-200 p-4 mt-4">
      <h2 class="font-semibold text-slate-900 mb-1">{{ t("costing.title") }}</h2>
      <p class="text-xs text-slate-500 mb-2">{{ t("costing.hint") }}</p>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-400">
            <th class="font-normal pb-1">{{ t("costing.material") }}</th>
            <th class="font-normal pb-1">{{ t("costing.consumption") }}</th>
            <th class="font-normal pb-1">{{ t("costing.unitCost") }}</th>
            <th class="font-normal pb-1">{{ t("costing.lineCost") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="line in cost.lines" :key="line.material_id" class="border-t border-slate-100">
            <td class="py-1.5">{{ line.material_name }}</td>
            <td class="py-1.5 text-slate-500">{{ line.consumption }} {{ line.unit }}</td>
            <td class="py-1.5 text-slate-500">{{ line.unit_cost }} €/{{ line.unit }}</td>
            <td class="py-1.5 font-medium text-slate-800">{{ line.line_cost.toFixed(2) }} €</td>
          </tr>
          <tr class="border-t border-slate-100">
            <td class="py-1.5">{{ t("costing.labor") }}</td>
            <td class="py-1.5 text-slate-500">{{ cost.labor_hours }} h</td>
            <td class="py-1.5 text-slate-500">{{ cost.hourly_rate }} €/h</td>
            <td class="py-1.5 font-medium text-slate-800">{{ cost.labor_cost.toFixed(2) }} €</td>
          </tr>
        </tbody>
      </table>

      <div class="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between">
        <span class="font-semibold text-slate-900">{{ t("costing.costPrice") }}</span>
        <span class="font-semibold text-slate-900">{{ cost.cost_price.toFixed(2) }} €</span>
      </div>

      <div class="mt-3 pt-3 border-t border-slate-200 space-y-1">
        <div class="flex items-center justify-between text-sm">
          <span class="text-slate-600">{{ t("costing.suggestedPrice", { n: cost.margin_percent }) }}</span>
          <span class="font-semibold text-indigo-700">{{ cost.suggested_sale_price.toFixed(2) }} €</span>
        </div>
        <div class="flex items-center justify-between text-sm">
          <span class="text-slate-600">{{ t("costing.currentPrice") }}</span>
          <span class="font-medium text-slate-800">{{ cost.current_sale_price.toFixed(2) }} €</span>
        </div>
        <p v-if="priceDelta !== null" class="text-xs mt-1" :class="priceDelta < 0 ? 'text-red-600' : 'text-green-600'">
          {{ priceDelta < 0 ? t("costing.belowSuggested", { n: Math.abs(priceDelta).toFixed(2) }) : t("costing.aboveSuggested", { n: priceDelta.toFixed(2) }) }}
        </p>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mt-4">
      <h2 class="font-semibold text-slate-900 mb-2">{{ t("knifeModels.process") }}</h2>
      <ol class="space-y-3">
        <li v-for="(recipe, i) in recipesByModel" :key="recipe!.id">
          <p class="text-sm font-medium text-slate-800">{{ i + 1 }}. {{ recipe!.name }}</p>
          <ol class="mt-1 ml-4 list-decimal list-inside text-sm text-slate-600 space-y-0.5">
            <li v-for="s in recipe!.steps" :key="s.id">
              {{ s.description }}
              <span class="text-slate-400">
                <template v-if="s.temperature_c !== null">— {{ s.temperature_c }}°C</template>
                <template v-if="s.duration_minutes !== null">, {{ s.duration_minutes }} min</template>
                <template v-if="s.medium">, {{ s.medium }}</template>
              </span>
            </li>
          </ol>
        </li>
      </ol>
    </div>
  </div>
</template>
