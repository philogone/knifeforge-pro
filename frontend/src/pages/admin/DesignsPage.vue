<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError, saveBlob } from "@/composables/useApi";
import { documentToSvg } from "@/editor/svgPreview";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { DesignKind, DesignSummary, DesignTemplate } from "@/types";

const { t, num } = useI18n();
const store = useAppStore();
const router = useRouter();
const route = useRoute();

const kinds: DesignKind[] = ["blade", "handle_scale", "guard", "bolster", "sheath", "template", "other"];

const templates = ref<DesignTemplate[]>([]);
const designs = ref<DesignSummary[]>([]);
const thumbs = reactive<Record<number, string>>({});
const loading = ref(true);
const error = ref("");
const showNew = ref(false);

const filter = reactive({ knife_model_id: 0, material_id: 0, kind: "" as "" | DesignKind });

const form = reactive({
  template: "blank",
  name: "",
  kind: "blade" as DesignKind,
  knife_model_id: 0,
  material_id: 0,
});

async function load() {
  designs.value = await store.fetchDesigns({
    knife_model_id: filter.knife_model_id || undefined,
    material_id: filter.material_id || undefined,
  });
  // thumbnails need the document: fetch lazily, once per design
  for (const d of designs.value) {
    if (thumbs[d.id] !== undefined) continue;
    thumbs[d.id] = "";
    store
      .fetchDesign(d.id)
      .then((full) => {
        thumbs[d.id] = documentToSvg(full.document);
      })
      .catch(() => {
        thumbs[d.id] = "";
      });
  }
}

onMounted(async () => {
  try {
    const [tpls] = await Promise.all([store.fetchDesignTemplates(), store.fetchMaterials(), store.fetchKnifeModels()]);
    templates.value = tpls;
    // "Nouveau gabarit" from a knife model page: open the form already linked to it
    const fromModel = Number(route.query.model);
    if (fromModel) {
      form.knife_model_id = fromModel;
      const blade = store.knifeModels.find((m) => m.id === fromModel)?.materials.find((m) => m.role === "blade");
      if (blade) form.material_id = blade.material_id;
      showNew.value = true;
    }
    await load();
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : t("common.error");
  } finally {
    loading.value = false;
  }
});

watch(() => [filter.knife_model_id, filter.material_id], () => void load());

const visible = computed(() => designs.value.filter((d) => !filter.kind || d.kind === filter.kind));

watch(
  () => form.template,
  (key) => {
    const tpl = templates.value.find((x) => x.key === key);
    if (tpl) form.kind = tpl.kind;
  },
);

async function create() {
  error.value = "";
  const tpl = templates.value.find((x) => x.key === form.template);
  if (!tpl) return;
  try {
    const created = await store.createDesign({
      name: form.name.trim() || tpl.name,
      kind: form.kind,
      knife_model_id: form.knife_model_id || null,
      material_id: form.material_id || null,
      document: tpl.document,
    });
    router.push(`/designs/${created.id}`);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : t("common.error");
  }
}

async function duplicate(d: DesignSummary) {
  const copy = await store.duplicateDesign(d.id);
  router.push(`/designs/${copy.id}`);
}

async function remove(d: DesignSummary) {
  if (!confirm(`${t("common.delete")} « ${d.name} » ?`)) return;
  await store.deleteDesign(d.id);
  await load();
}

async function download(d: DesignSummary, kind: "export.svg" | "export.dxf") {
  try {
    const blob = await store.downloadDesignFile(d.id, kind);
    saveBlob(blob, `${d.name.replace(/[^\w.-]+/g, "_")}.${kind.split(".")[1]}`);
  } catch (err) {
    alert(t("designs.exportFailed", { error: err instanceof ApiError ? err.message : "?" }));
  }
}

function templateLabel(key: string, fallback: string) {
  const k = `designs.template.${key}`;
  const label = t(k);
  return label === k ? fallback : label;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <div class="flex items-start justify-between flex-wrap gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">{{ t("designs.title") }}</h1>
        <p class="text-sm text-slate-500 mt-1 max-w-2xl">{{ t("designs.subtitle") }}</p>
      </div>
      <button class="bg-accent-600 hover:bg-accent-700 text-white text-sm font-medium rounded-lg px-4 py-2" @click="showNew = !showNew">
        + {{ t("designs.new") }}
      </button>
    </div>

    <form v-if="showNew" class="bg-white rounded-xl border border-slate-200 p-4 mb-6 space-y-4" @submit.prevent="create">
      <div>
        <label class="block text-xs text-slate-500 mb-2">{{ t("designs.template") }}</label>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
          <button
            v-for="tpl in templates"
            :key="tpl.key"
            type="button"
            class="rounded-lg border p-2 text-left text-xs"
            :class="form.template === tpl.key ? 'border-accent-500 ring-2 ring-accent-200' : 'border-slate-200 hover:border-slate-300'"
            @click="form.template = tpl.key"
          >
            <div class="h-20 mb-1 [&>svg]:w-full [&>svg]:h-full" v-html="documentToSvg(tpl.document)"></div>
            {{ templateLabel(tpl.key, tpl.name) }}
          </button>
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label class="block text-xs text-slate-500 mb-1">{{ t("common.name") }}</label>
          <input v-model="form.name" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">{{ t("designs.kind") }}</label>
          <select v-model="form.kind" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option v-for="k in kinds" :key="k" :value="k">{{ t(`designs.kind.${k}`) }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">{{ t("designs.knifeModel") }}</label>
          <select v-model.number="form.knife_model_id" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option :value="0">{{ t("designs.none") }}</option>
            <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">{{ t("designs.material") }}</label>
          <select v-model.number="form.material_id" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option :value="0">{{ t("designs.none") }}</option>
            <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
      </div>
      <div class="flex gap-2">
        <button type="submit" class="bg-accent-600 hover:bg-accent-700 text-white text-sm font-medium rounded-lg px-4 py-2">{{ t("designs.create") }}</button>
        <button type="button" class="text-sm text-slate-500 px-4 py-2" @click="showNew = false">{{ t("common.cancel") }}</button>
      </div>
    </form>

    <p v-if="error" class="text-sm text-red-600 mb-4">{{ error }}</p>

    <div class="flex flex-wrap gap-3 mb-4 text-sm">
      <select v-model="filter.kind" class="rounded-lg border border-slate-300 px-3 py-1.5">
        <option value="">{{ t("designs.kind") }} : {{ t("designs.filterAll") }}</option>
        <option v-for="k in kinds" :key="k" :value="k">{{ t(`designs.kind.${k}`) }}</option>
      </select>
      <select v-model.number="filter.knife_model_id" class="rounded-lg border border-slate-300 px-3 py-1.5">
        <option :value="0">{{ t("designs.knifeModel") }} : {{ t("designs.filterAll") }}</option>
        <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
      <select v-model.number="filter.material_id" class="rounded-lg border border-slate-300 px-3 py-1.5">
        <option :value="0">{{ t("designs.material") }} : {{ t("designs.filterAll") }}</option>
        <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
    </div>

    <p v-if="loading" class="text-sm text-slate-500">{{ t("common.loading") }}</p>
    <p v-else-if="!visible.length" class="text-sm text-slate-500">{{ t("designs.empty") }}</p>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="d in visible" :key="d.id" class="bg-white rounded-xl border border-slate-200 overflow-hidden flex flex-col">
        <router-link :to="`/designs/${d.id}`" class="block h-40 bg-slate-50 border-b border-slate-100 p-3 [&>svg]:w-full [&>svg]:h-full" v-html="thumbs[d.id]"></router-link>
        <div class="p-3 flex-1 flex flex-col gap-1">
          <div class="flex items-center gap-2 flex-wrap">
            <router-link :to="`/designs/${d.id}`" class="font-medium text-slate-900 hover:text-accent-600">{{ d.name }}</router-link>
            <span class="text-xs bg-accent-50 text-accent-700 rounded px-1.5 py-0.5">{{ t(`designs.kind.${d.kind}`) }}</span>
            <span v-if="d.is_mock" class="text-xs text-slate-500 bg-slate-100 rounded px-1.5 py-0.5">{{ t("common.demo") }}</span>
          </div>
          <p class="text-xs text-slate-500">
            {{ num(d.width_mm) }} × {{ num(d.height_mm) }} mm · {{ num(d.area_mm2 / 100) }} cm² · {{ d.part_count }} {{ t("designs.parts") }}
          </p>
          <p v-if="d.knife_model_name || d.material_name" class="text-xs text-slate-500">
            <span v-if="d.knife_model_name">🔪 {{ d.knife_model_name }}</span>
            <span v-if="d.knife_model_name && d.material_name"> · </span>
            <span v-if="d.material_name">▦ {{ d.material_name }}</span>
          </p>
          <p class="text-xs text-slate-500">{{ t("designs.updated") }} {{ fmtDate(d.updated_at) }}</p>
          <div class="mt-auto pt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm">
            <router-link :to="`/designs/${d.id}`" class="text-accent-600">{{ t("designs.open") }}</router-link>
            <button class="text-slate-600" @click="duplicate(d)">{{ t("designs.duplicate") }}</button>
            <button class="text-slate-600" @click="download(d, 'export.svg')">{{ t("designs.exportSvg") }}</button>
            <button class="text-slate-600" @click="download(d, 'export.dxf')">{{ t("designs.exportDxf") }}</button>
            <button class="text-red-600 ml-auto" @click="remove(d)">{{ t("common.delete") }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
