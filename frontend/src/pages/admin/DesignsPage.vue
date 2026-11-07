<script setup lang="ts">
import ListToolbar from "@/components/ListToolbar.vue";
import { byText, useListSearch } from "@/composables/useListSearch";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { saveBlob } from "@/composables/useApi";
import { documentToSvg } from "@/editor/svgPreview";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
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
    error.value = errorMessage(err, t, "common.error");
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
    error.value = errorMessage(err, t, "common.error");
  }
}

async function duplicate(d: DesignSummary) {
  const copy = await store.duplicateDesign(d.id);
  router.push(`/designs/${copy.id}`);
}

async function remove(d: DesignSummary) {
  if (!confirm(t("common.confirmDeleteNamed", { name: d.name }))) return;
  await store.deleteDesign(d.id);
  await load();
}

async function download(d: DesignSummary, kind: "export.svg" | "export.dxf") {
  try {
    const blob = await store.downloadDesignFile(d.id, kind);
    saveBlob(blob, `${d.name.replace(/[^\w.-]+/g, "_")}.${kind.split(".")[1]}`);
  } catch (err) {
    alert(t("designs.exportFailed", { error: errorMessage(err, t) }));
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

// ---- search and sort, on top of the server-side model / material filters
const list = useListSearch(
  () => visible.value,
  (d) => [d.name, d.knife_model_name, d.material_name, t(`designs.kind.${d.kind}`)],
  [
    { key: "recent", label: "", compare: (a, b) => b.updated_at.localeCompare(a.updated_at) },
    { key: "name", label: "", compare: (a, b) => byText(a.name, b.name) },
    { key: "unlinked", label: "", compare: (a, b) => Number(!!a.knife_model_id && !!a.material_id) - Number(!!b.knife_model_id && !!b.material_id) || byText(a.name, b.name) },
  ],
);
const sortOptions = computed(() => [
  { key: "recent", label: t("list.sort.recentlyEdited") },
  { key: "name", label: t("list.sort.name") },
  { key: "unlinked", label: t("list.sort.unlinkedFirst") },
]);
</script>

<template>
  <div class="page max-w-6xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("designs.title") }}</h1>
        <p class="page-lead">{{ t("designs.subtitle") }}</p>
      </div>
      <button v-if="!showNew" class="btn btn-primary" @click="showNew = true">+ {{ t("designs.new") }}</button>
    </header>

    <form v-if="showNew" class="sheet p-4 mb-6 space-y-4" @submit.prevent="create">
      <div>
        <label class="field-label mb-2">{{ t("designs.template") }}</label>
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
          <label class="field-label" for="designs-f1">{{ t("common.name") }}</label>
          <input id="designs-f1" v-model="form.name" class="input w-full" />
        </div>
        <div>
          <label class="field-label" for="designs-f2">{{ t("designs.kind") }}</label>
          <select id="designs-f2" v-model="form.kind" class="input w-full">
            <option v-for="k in kinds" :key="k" :value="k">{{ t(`designs.kind.${k}`) }}</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="designs-f3">{{ t("designs.knifeModel") }}</label>
          <select id="designs-f3" v-model.number="form.knife_model_id" class="input w-full">
            <option :value="0">{{ t("designs.none") }}</option>
            <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="designs-f4">{{ t("designs.material") }}</label>
          <select id="designs-f4" v-model.number="form.material_id" class="input w-full">
            <option :value="0">{{ t("designs.none") }}</option>
            <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
      </div>
      <div class="flex gap-2">
        <button type="submit" class="btn btn-primary">{{ t("designs.create") }}</button>
        <button type="button" class="btn btn-outline" @click="showNew = false">{{ t("common.cancel") }}</button>
      </div>
    </form>

    <p v-if="error" class="text-sm text-red-600 mb-4">{{ error }}</p>

    <ListToolbar
      v-model:query="list.query.value"
      v-model:sort="list.sortKey.value"
      :placeholder="t('list.search.designs')"
      :sorts="sortOptions"
      :shown="list.visible.value.length"
      :total="designs.length"
    />
    <div class="flex flex-wrap gap-3 mb-4 text-sm">
      <select v-model="filter.kind" :aria-label="t('designs.kind')" class="input-sm">
        <option value="">{{ t("designs.kind") }} : {{ t("designs.filterAll") }}</option>
        <option v-for="k in kinds" :key="k" :value="k">{{ t(`designs.kind.${k}`) }}</option>
      </select>
      <select v-model.number="filter.knife_model_id" :aria-label="t('designs.knifeModel')" class="input-sm">
        <option :value="0">{{ t("designs.knifeModel") }} : {{ t("designs.filterAll") }}</option>
        <option v-for="m in store.knifeModels" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
      <select v-model.number="filter.material_id" :aria-label="t('designs.material')" class="input-sm">
        <option :value="0">{{ t("designs.material") }} : {{ t("designs.filterAll") }}</option>
        <option v-for="m in store.materials" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
    </div>

    <p v-if="loading" class="text-sm text-slate-500">{{ t("common.loading") }}</p>
    <p v-else-if="!designs.length" class="text-sm text-slate-500">{{ t("designs.empty") }}</p>
    <p v-else-if="!list.visible.value.length" class="sheet p-6 text-sm text-slate-600">{{ t("list.noMatch") }}</p>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="d in list.visible.value" :key="d.id" class="sheet overflow-hidden flex flex-col">
        <router-link
          v-if="d.part_count"
          :to="`/designs/${d.id}`"
          :aria-label="d.name"
          class="block h-40 bg-slate-50 border-b border-slate-100 p-4 [&>svg]:w-full [&>svg]:h-full"
          v-html="thumbs[d.id]"
        ></router-link>
        <router-link v-else :to="`/designs/${d.id}`" class="h-40 bg-slate-50 border-b border-slate-100 p-4 flex items-center justify-center text-center text-sm text-slate-500">
          {{ t("designs.emptyThumb") }}
        </router-link>
        <div class="p-3 flex-1 flex flex-col gap-1">
          <router-link :to="`/designs/${d.id}`" class="font-semibold text-slate-900 hover:text-accent-700 truncate" :title="d.name">{{ d.name }}</router-link>
          <div class="flex items-center gap-1.5">
            <span class="tag tag-accent">{{ t(`designs.kind.${d.kind}`) }}</span>
            <span v-if="d.is_mock" class="tag tag-neutral">{{ t("common.demo") }}</span>
          </div>
          <p class="text-xs text-slate-600 tabular-nums">
            {{ num(d.width_mm) }} × {{ num(d.height_mm) }} mm · {{ num(d.area_mm2 / 100) }} cm² · {{ t(d.part_count > 1 ? "designs.partsMany" : "designs.partsOne", { n: d.part_count }) }}
          </p>
          <dl class="text-xs grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 mt-0.5">
            <dt class="text-slate-500">{{ t("designs.knifeModel") }}</dt>
            <dd :class="d.knife_model_name ? 'text-slate-700' : 'text-amber-800'">{{ d.knife_model_name ?? t("designs.notLinked") }}</dd>
            <dt class="text-slate-500">{{ t("designs.material") }}</dt>
            <dd :class="d.material_name ? 'text-slate-700' : 'text-amber-800'">{{ d.material_name ?? t("designs.notLinked") }}</dd>
          </dl>
          <p class="text-xs text-slate-500">{{ t("designs.updated") }} {{ fmtDate(d.updated_at) }}</p>
          <div class="mt-auto pt-3 border-t border-slate-100 flex flex-wrap items-center gap-x-4 gap-y-1">
            <router-link :to="`/designs/${d.id}`" class="link-action font-medium">{{ t("designs.open") }}</router-link>
            <button class="link-action" @click="duplicate(d)">{{ t("designs.duplicate") }}</button>
            <button class="link-action" @click="download(d, 'export.svg')">{{ t("designs.exportSvg") }}</button>
            <button class="link-action" @click="download(d, 'export.dxf')">{{ t("designs.exportDxf") }}</button>
            <button class="link-danger ml-auto" @click="remove(d)">{{ t("common.delete") }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
