<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import ListToolbar from "@/components/ListToolbar.vue";
import { byText, useListSearch } from "@/composables/useListSearch";
import { DOCUMENT_STATUS_TAG } from "@/constants/referenceData";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { DocumentKind, SalesDocument } from "@/types";

const { t, locale, money } = useI18n();
const store = useAppStore();
const route = useRoute();
const router = useRouter();

const docs = ref<SalesDocument[]>([]);
const loading = ref(true);
const error = ref("");
const kind = ref<"" | DocumentKind>((route.query.kind as DocumentKind) || "");
const customerId = computed(() => Number(route.query.customer) || undefined);

async function load() {
  loading.value = true;
  try {
    docs.value = await store.fetchDocuments({ customer_id: customerId.value });
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(customerId, load);

async function create(k: "quote" | "invoice") {
  const doc = await store.createDocument({ kind: k, customer_id: customerId.value ?? null, lines: [] });
  router.push(`/documents/${doc.id}`);
}

const list = useListSearch(
  () => docs.value.filter((d) => !kind.value || d.kind === kind.value),
  (d) => [d.number, d.customer_name, ...d.lines.map((l) => l.description)],
  [
    { key: "recent", label: "", compare: (a, b) => (b.issue_date ?? b.created_at).localeCompare(a.issue_date ?? a.created_at) },
    { key: "number", label: "", compare: (a, b) => byText(b.number ?? "", a.number ?? "") },
    { key: "amount", label: "", compare: (a, b) => Number(b.total_ttc) - Number(a.total_ttc) },
  ],
);
const sortOptions = computed(() => [
  { key: "recent", label: t("list.sort.recent") },
  { key: "number", label: t("documents.sort.number") },
  { key: "amount", label: t("documents.sort.amount") },
]);

const kinds: ("" | DocumentKind)[] = ["", "quote", "invoice", "credit_note"];
const unpaidTotal = computed(() =>
  docs.value.filter((d) => d.kind === "invoice" && d.status === "issued").reduce((sum, d) => sum + Number(d.total_ttc), 0),
);

function fmtDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString(locale.value === "fr" ? "fr-FR" : "en-GB") : "—";
}
</script>

<template>
  <div class="page max-w-7xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("documents.title") }}</h1>
        <p class="page-lead">{{ t("documents.lead") }}</p>
      </div>
      <div class="flex gap-2">
        <button class="btn btn-outline" @click="create('quote')">+ {{ t("documents.newQuote") }}</button>
        <button class="btn btn-primary" @click="create('invoice')">+ {{ t("documents.newInvoice") }}</button>
      </div>
    </header>
    <p v-if="error" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div class="mb-4 flex flex-wrap items-center gap-2" role="tablist">
      <button
        v-for="k in kinds"
        :key="k || 'all'"
        role="tab"
        :aria-selected="kind === k"
        class="px-3 py-1.5 rounded-lg text-sm border transition-colors"
        :class="kind === k ? 'bg-slate-800 text-paper border-slate-800' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
        @click="kind = k"
      >
        {{ k ? t(`documents.kinds.${k}`) : t("designs.filterAll") }}
      </button>
      <p v-if="unpaidTotal" class="ml-auto text-sm text-slate-600">
        {{ t("documents.unpaid") }}{{ t("common.colon") }} <strong class="text-slate-900 tabular-nums">{{ money(unpaidTotal) }}</strong>
      </p>
    </div>

    <ListToolbar
      v-if="list.total.value"
      v-model:query="list.query.value"
      v-model:sort="list.sortKey.value"
      :placeholder="t('documents.search')"
      :sorts="sortOptions"
      :shown="list.visible.value.length"
      :total="list.total.value"
    />

    <p v-if="loading" class="text-sm text-slate-500">{{ t("common.loading") }}</p>
    <p v-else-if="!docs.length" class="sheet p-6 text-sm text-slate-600">{{ t("documents.empty") }}</p>
    <p v-else-if="!list.visible.value.length" class="sheet p-6 text-sm text-slate-600">{{ t("list.noMatch") }}</p>

    <div v-else class="sheet overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-500 border-b border-slate-200">
              <th class="font-normal px-4 py-2">{{ t("documents.col.number") }}</th>
              <th class="font-normal px-4 py-2">{{ t("documents.col.customer") }}</th>
              <th class="font-normal px-4 py-2">{{ t("documents.col.date") }}</th>
              <th class="font-normal px-4 py-2">{{ t("documents.col.status") }}</th>
              <th class="font-normal px-4 py-2 text-right">{{ t("documents.col.total") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="d in list.visible.value"
              :key="d.id"
              class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
              @click="router.push(`/documents/${d.id}`)"
            >
              <td class="px-4 py-2.5">
                <router-link :to="`/documents/${d.id}`" class="font-medium text-slate-900 hover:underline" @click.stop>
                  {{ t(`documents.kinds.${d.kind}`) }} {{ d.number ?? t("documents.draft") }}
                </router-link>
              </td>
              <td class="px-4 py-2.5 text-slate-700">{{ d.customer_name ?? "—" }}</td>
              <td class="px-4 py-2.5 text-slate-600 tabular-nums">{{ fmtDate(d.issue_date ?? d.created_at) }}</td>
              <td class="px-4 py-2.5"><span class="tag font-medium" :class="DOCUMENT_STATUS_TAG[d.status]">{{ t(`documents.status.${d.kind}.${d.status}`) }}</span></td>
              <td class="px-4 py-2.5 text-right tabular-nums font-medium" :class="d.kind === 'credit_note' ? 'text-red-700' : 'text-slate-900'">
                {{ d.kind === "credit_note" ? "− " : "" }}{{ money(Number(d.total_ttc)) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <p class="mt-4 text-xs text-slate-500 max-w-prose">{{ t("documents.einvoicingNote") }}</p>
  </div>
</template>
