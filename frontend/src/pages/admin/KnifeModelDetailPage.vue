<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { documentToSvg } from "@/editor/svgPreview";
import { formatDecimal, useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { CostBreakdown, DesignSummary } from "@/types";

const { t, money, qty, num, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const store = useAppStore();
const modelId = Number(route.params.id);

onMounted(async () => {
  await Promise.all([store.fetchKnifeModels(), store.fetchTreatmentRecipes(), loadDesigns()]);
  cost.value = await store.fetchCostBreakdown(modelId);
});

// Templates (gabarits) linked to this model: the nesting takes an order's parts from them,
// one template per material the model uses.
const allDesigns = ref<DesignSummary[]>([]);
const linkedDesigns = computed(() => allDesigns.value.filter((d) => d.knife_model_id === modelId));
const attachable = computed(() => allDesigns.value.filter((d) => d.knife_model_id !== modelId));
const attachId = ref(0);
const designError = ref("");

async function loadDesigns() {
  await store.fetchDesigns();
  allDesigns.value = store.designs;
}



async function setDesignModel(id: number, knifeModelId: number | null) {
  designError.value = "";
  try {
    await store.updateDesign(id, { knife_model_id: knifeModelId });
    await loadDesigns();
    attachId.value = 0;
  } catch (err) {
    designError.value = errorMessage(err, t, "common.error");
  }
}

/** model materials that no linked template covers: their parts can't be nested yet */
const uncoveredMaterials = computed(() =>
  (model.value?.materials ?? []).filter(
    (m) => m.blank_length_mm && !linkedDesigns.value.some((d) => d.material_id === m.material_id),
  ),
);

const model = computed(() => store.knifeModels.find((m) => m.id === modelId));

// Client view: what the maker turns towards a customer. No cost, margin, build time or
// shop tools; the knife, its materials, its process and its plans. Kept in the URL
// (?view=client) so the view survives a reload and can be bookmarked.
const clientView = computed(() => route.query.view === "client");
function setClientView(on: boolean) {
  router.replace({ query: { ...route.query, view: on ? "client" : undefined } });
}
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

const deleteError = ref("");

async function deleteModel() {
  if (!confirm(t("common.confirmDeleteNamed", { name: model.value?.name ?? "" }))) return;
  deleteError.value = "";
  try {
    await store.deleteKnifeModel(modelId);
    router.push("/knife-models");
  } catch (err) {
    deleteError.value = errorMessage(err, t, "common.deleteFailed");
  }
}

// drawings of the linked templates, for the client view
const thumbs = reactive<Record<number, string>>({});
watch(
  () => [clientView.value, linkedDesigns.value.map((d) => d.id).join(",")],
  () => {
    if (!clientView.value) return;
    for (const d of linkedDesigns.value) {
      if (thumbs[d.id] !== undefined || !d.part_count) continue;
      thumbs[d.id] = "";
      store
        .fetchDesign(d.id)
        .then((full) => (thumbs[d.id] = documentToSvg(full.document)))
        .catch(() => undefined);
    }
  },
  { immediate: true },
);
</script>

<template>
  <div v-if="model" class="page max-w-3xl">
    <router-link to="/knife-models" class="back-link">&larr; {{ t("common.backToList") }}</router-link>
    <div class="flex items-start justify-between gap-4 mt-1 flex-wrap">
      <div class="flex items-center gap-2 flex-wrap min-w-0">
        <h1 class="page-title">{{ model.name }}</h1>
        <span class="tag tag-accent">{{ t(`knifeModels.knifeType.${model.knife_type}`) }}</span>
      </div>
      <div class="flex items-center gap-4">
        <div class="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 text-sm" role="group" :aria-label="t('clientView.toggle')">
          <button class="px-3 py-1 rounded-md transition-colors" :class="!clientView ? 'bg-slate-800 text-white' : 'text-slate-600 hover:text-slate-900'" :aria-pressed="!clientView" @click="setClientView(false)">{{ t("clientView.workshop") }}</button>
          <button class="px-3 py-1 rounded-md transition-colors" :class="clientView ? 'bg-accent-600 text-white' : 'text-slate-600 hover:text-slate-900'" :aria-pressed="clientView" @click="setClientView(true)">{{ t("clientView.client") }}</button>
        </div>
        <template v-if="!clientView">
          <button class="link-action" @click="editModel">{{ t("common.edit") }}</button>
          <button class="link-danger" @click="deleteModel">{{ t("common.delete") }}</button>
        </template>
      </div>
    </div>

    <!-- client view: the knife as the customer sees it -->
    <template v-if="clientView">
      <p class="mt-3 text-3xl font-semibold tabular-nums text-slate-900">{{ money(model.sale_price) }}</p>

      <section v-if="linkedDesigns.length" class="mt-6 grid sm:grid-cols-2 gap-4" :aria-label="t('modelDesigns.title')">
        <article v-for="d in linkedDesigns" :key="d.id" class="sheet overflow-hidden">
          <div class="h-44 bg-slate-50 border-b border-slate-100 p-5 [&>svg]:w-full [&>svg]:h-full" v-html="thumbs[d.id] ?? ''"></div>
          <div class="p-4 flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="font-semibold text-slate-900 truncate">{{ d.name }}</p>
              <p class="text-xs text-slate-500 tabular-nums">{{ num(d.width_mm) }} × {{ num(d.height_mm) }} mm<span v-if="d.material_name"> · {{ d.material_name }}</span></p>
            </div>
            <router-link :to="{ path: `/designs/${d.id}`, query: { plan: '1' } }" class="btn btn-outline btn-sm shrink-0">{{ t("clientView.plan") }}</router-link>
          </div>
        </article>
      </section>

      <section class="sheet p-5 mt-4">
        <h2 class="sheet-title mb-3">{{ t("clientView.materials") }}</h2>
        <dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <template v-for="m in model.materials" :key="m.id">
            <dt class="text-slate-500">{{ t(`knifeModels.role.${m.role}`) }}</dt>
            <dd class="text-slate-900">{{ m.material_name }}</dd>
          </template>
        </dl>
      </section>

      <section v-if="recipesByModel.length" class="sheet p-5 mt-4">
        <h2 class="sheet-title mb-3">{{ t("clientView.process") }}</h2>
        <ol class="space-y-1.5 text-sm text-slate-800 list-decimal list-inside">
          <li v-for="recipe in recipesByModel" :key="recipe!.id">{{ recipe!.name }}</li>
        </ol>
      </section>
    </template>

    <template v-else>
    <p class="text-sm text-slate-500 mt-1">{{ t("knifeModels.buildTime") }}{{ t("common.colon") }} {{ t("knifeModels.hours", { n: model.base_labor_hours }) }} &middot; {{ money(model.sale_price) }}</p>

    <p v-if="deleteError" role="alert" class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ deleteError }}</p>

    <div class="sheet p-4 mt-6">
      <h2 class="sheet-title mb-2">{{ t("knifeModels.materialsRequired") }}</h2>
      <div class="-mx-1 overflow-x-auto">
      <table class="w-full text-sm">
        <tbody>
          <tr v-for="m in model.materials" :key="m.id" class="border-t border-slate-100 first:border-0">
            <td class="py-2 font-medium text-slate-800">{{ m.material_name }}</td>
            <td class="py-2 text-slate-500">{{ t(`knifeModels.role.${m.role}`) }}</td>
            <td class="py-2 text-slate-500">
              <span v-if="m.blank_length_mm" class="tabular-nums">{{ [m.blank_length_mm, m.blank_width_mm, m.blank_thickness_mm].filter((v) => v).map((v) => num(v!, 1)).join(" × ") }} mm</span>
              <span v-else class="tabular-nums">{{ qty(m.quantity, "unit") }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>


    <section class="sheet p-4 mt-4" aria-labelledby="model-designs">
      <div class="flex items-center justify-between gap-3">
        <h2 id="model-designs" class="font-semibold text-slate-900">{{ t("modelDesigns.title") }}</h2>
        <router-link :to="{ path: '/designs', query: { model: String(modelId) } }" class="text-sm text-accent-700 hover:underline">
          + {{ t("modelDesigns.new") }}
        </router-link>
      </div>
      <p class="text-xs text-slate-500 mt-1">{{ t("modelDesigns.hint") }}</p>

      <ul v-if="linkedDesigns.length" class="mt-3 divide-y divide-slate-100">
        <li v-for="d in linkedDesigns" :key="d.id" class="flex items-center gap-3 py-2 text-sm">
          <router-link :to="`/designs/${d.id}`" class="font-medium text-slate-800 hover:text-accent-700">{{ d.name }}</router-link>
          <span class="text-slate-500">{{ d.material_name ?? t("modelDesigns.noMaterial") }}</span>
          <router-link :to="{ path: `/designs/${d.id}`, query: { plan: '1' } }" class="ml-auto text-xs link-action">{{ t("clientView.plan") }}</router-link>
          <button class="text-xs text-slate-500 hover:text-red-700" @click="setDesignModel(d.id, null)">{{ t("modelDesigns.detach") }}</button>
        </li>
      </ul>
      <p v-else class="mt-3 text-sm text-slate-600">{{ t("modelDesigns.empty") }}</p>

      <p v-for="m in uncoveredMaterials" :key="m.id" class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
        {{ t("modelDesigns.uncovered", { material: m.material_name ?? "" }) }}
      </p>

      <form v-if="attachable.length" class="mt-3 flex gap-2" @submit.prevent="attachId && setDesignModel(attachId, modelId)">
        <label class="sr-only" for="attach-design">{{ t("modelDesigns.attach") }}</label>
        <select id="attach-design" v-model.number="attachId" class="flex-1 input-sm text-sm">
          <option :value="0">{{ t("modelDesigns.attachPlaceholder") }}</option>
          <option v-for="d in attachable" :key="d.id" :value="d.id">
            {{ d.name }}{{ d.knife_model_name ? ` (${d.knife_model_name})` : "" }}
          </option>
        </select>
        <button type="submit" :disabled="!attachId" class="rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50">{{ t("modelDesigns.attach") }}</button>
      </form>
      <p v-if="designError" role="alert" class="mt-2 text-sm text-red-700">{{ designError }}</p>
    </section>

    <div v-if="cost" class="sheet p-4 mt-4">
      <h2 class="sheet-title mb-1">{{ t("costing.title") }}</h2>
      <p class="text-xs text-slate-500 mb-2">{{ t("costing.hint") }}</p>
      <div class="-mx-1 overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500">
            <th class="font-normal pb-1">{{ t("costing.material") }}</th>
            <th class="font-normal pb-1">{{ t("costing.consumption") }}</th>
            <th class="font-normal pb-1">{{ t("costing.unitCost") }}</th>
            <th class="font-normal pb-1">{{ t("costing.lineCost") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="line in cost.lines" :key="line.material_id" class="border-t border-slate-100">
            <td class="py-1.5">{{ line.material_name }}</td>
            <td class="py-1.5 text-slate-500">{{ qty(line.consumption, line.unit) }}</td>
            <td class="py-1.5 text-slate-500">{{ formatDecimal(line.unit_cost, locale, 6) }} €/{{ line.unit === "unit" ? t("common.unitOne") : line.unit }}</td>
            <td class="py-1.5 font-medium text-slate-800">{{ money(line.line_cost) }}</td>
          </tr>
          <tr class="border-t border-slate-100">
            <td class="py-1.5">{{ t("costing.labor") }}</td>
            <td class="py-1.5 text-slate-500">{{ cost.labor_hours }} h</td>
            <td class="py-1.5 text-slate-500">{{ cost.hourly_rate }} €/h</td>
            <td class="py-1.5 font-medium text-slate-800">{{ money(cost.labor_cost) }}</td>
          </tr>
        </tbody>
      </table>
      </div>

      <div class="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between">
        <span class="font-semibold text-slate-900">{{ t("costing.costPrice") }}</span>
        <span class="font-semibold text-slate-900">{{ money(cost.cost_price) }}</span>
      </div>

      <div class="mt-3 pt-3 border-t border-slate-200 space-y-1">
        <div class="flex items-center justify-between text-sm">
          <span class="text-slate-600">{{ t("costing.suggestedPrice", { n: cost.margin_percent }) }}</span>
          <span class="font-semibold text-accent-700">{{ money(cost.suggested_sale_price) }}</span>
        </div>
        <div class="flex items-center justify-between text-sm">
          <span class="text-slate-600">{{ t("costing.currentPrice") }}</span>
          <span class="font-medium text-slate-800">{{ money(cost.current_sale_price) }}</span>
        </div>
        <p v-if="priceDelta !== null" class="text-xs mt-1" :class="priceDelta < 0 ? 'text-red-600' : 'text-green-700'">
          {{ priceDelta < 0 ? t("costing.belowSuggested", { n: money(Math.abs(priceDelta)) }) : t("costing.aboveSuggested", { n: money(priceDelta) }) }}
        </p>
      </div>
    </div>

    <div class="sheet p-4 mt-4">
      <h2 class="sheet-title mb-2">{{ t("knifeModels.process") }}</h2>
      <ol class="space-y-3">
        <li v-for="(recipe, i) in recipesByModel" :key="recipe!.id">
          <p class="text-sm font-medium text-slate-800">{{ i + 1 }}. {{ recipe!.name }}</p>
          <ol class="mt-1 ml-4 list-decimal list-inside text-sm text-slate-600 space-y-0.5">
            <li v-for="s in recipe!.steps" :key="s.id">
              {{ s.description }}
              <span class="text-slate-500">— {{ [s.temperature_c !== null ? `${s.temperature_c} °C` : "", s.duration_minutes !== null ? `${s.duration_minutes} min` : "", s.medium ?? ""].filter(Boolean).join(" · ") }}</span>
            </li>
          </ol>
        </li>
      </ol>
    </div>
    </template>
  </div>
</template>
