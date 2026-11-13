<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import { saveBlob } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { AccountingPeriod } from "@/types";

const { t, money, locale } = useI18n();
const store = useAppStore();

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const now = new Date();

type Preset = "month" | "lastMonth" | "quarter" | "lastQuarter" | "year" | "lastYear" | "custom";
const presets: Preset[] = ["month", "lastMonth", "quarter", "lastQuarter", "year", "lastYear", "custom"];

function range(p: Preset): [string, string] | null {
  const y = now.getFullYear();
  const m = now.getMonth();
  const q = Math.floor(m / 3);
  switch (p) {
    case "month": return [iso(new Date(y, m, 1)), iso(new Date(y, m + 1, 0))];
    case "lastMonth": return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
    case "quarter": return [iso(new Date(y, 3 * q, 1)), iso(new Date(y, 3 * q + 3, 0))];
    case "lastQuarter": return [iso(new Date(y, 3 * q - 3, 1)), iso(new Date(y, 3 * q, 0))];
    case "year": return [iso(new Date(y, 0, 1)), iso(new Date(y, 11, 31))];
    case "lastYear": return [iso(new Date(y - 1, 0, 1)), iso(new Date(y - 1, 11, 31))];
    default: return null;
  }
}

const filter = reactive({ preset: "year" as Preset, start: range("year")![0], end: range("year")![1], granularity: "month" as "month" | "quarter" });
const periods = ref<AccountingPeriod[]>([]);
const franchise = ref(true);
const loading = ref(false);
const error = ref("");

watch(() => filter.preset, (p) => {
  const r = range(p);
  if (r) [filter.start, filter.end] = r;
});

async function load() {
  if (!filter.start || !filter.end) return;
  loading.value = true;
  error.value = "";
  try {
    const r = await store.accountingSummary(filter.start, filter.end, filter.granularity);
    periods.value = r.periods;
    franchise.value = r.franchise;
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(() => [filter.start, filter.end, filter.granularity], load);

const rates = computed(() => [...new Set(periods.value.flatMap((p) => p.vat.map((v) => v.rate)))].sort((a, b) => a - b));
const vatOf = (p: AccountingPeriod, rate: number) => p.vat.find((v) => v.rate === rate);
const sum = (f: (p: AccountingPeriod) => number) => periods.value.reduce((s, p) => s + f(p), 0);
const totalVat = (p: AccountingPeriod) => p.vat.reduce((s, v) => s + v.vat, 0);

function periodLabel(p: AccountingPeriod) {
  if (p.key.includes("-T")) return t("accounting.quarterLabel", { q: p.key.split("-T")[1], y: p.key.slice(0, 4) });
  return new Date(`${p.start}T00:00:00`).toLocaleDateString(locale.value === "fr" ? "fr-FR" : "en-GB", { month: "long", year: "numeric" });
}

async function download(kind: "journal.txt" | "sales.csv") {
  error.value = "";
  try {
    const blob = await store.accountingFile(kind, filter.start, filter.end);
    const stem = kind === "journal.txt" ? "journal-ventes" : "ventes";
    saveBlob(blob, `${stem}_${filter.start}_${filter.end}.${kind.split(".")[1]}`);
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}
</script>

<template>
  <div class="page max-w-7xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("accounting.title") }}</h1>
        <p class="page-lead">{{ t("accounting.lead") }}</p>
      </div>
    </header>
    <p v-if="error" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <section class="sheet p-4 mb-4 flex flex-wrap items-end gap-3">
      <label class="block">
        <span class="field-label">{{ t("accounting.period") }}</span>
        <select v-model="filter.preset" class="input">
          <option v-for="p in presets" :key="p" :value="p">{{ t(`accounting.presets.${p}`) }}</option>
        </select>
      </label>
      <label class="block">
        <span class="field-label">{{ t("accounting.from") }}</span>
        <input v-model="filter.start" type="date" class="input" @input="filter.preset = 'custom'" />
      </label>
      <label class="block">
        <span class="field-label">{{ t("accounting.to") }}</span>
        <input v-model="filter.end" type="date" class="input" @input="filter.preset = 'custom'" />
      </label>
      <label class="block">
        <span class="field-label">{{ t("accounting.by") }}</span>
        <select v-model="filter.granularity" class="input">
          <option value="month">{{ t("accounting.byMonth") }}</option>
          <option value="quarter">{{ t("accounting.byQuarter") }}</option>
        </select>
      </label>
      <div class="flex flex-wrap gap-2 ml-auto">
        <button class="btn btn-outline" :title="t('accounting.journalHint')" @click="download('journal.txt')">{{ t("accounting.journal") }}</button>
        <button class="btn btn-outline" :title="t('accounting.salesHint')" @click="download('sales.csv')">{{ t("accounting.sales") }}</button>
      </div>
    </section>

    <section class="sheet p-4">
      <h2 class="sheet-title mb-1">{{ franchise ? t("accounting.turnoverTitle") : t("accounting.vatTitle") }}</h2>
      <p class="text-sm text-slate-600 mb-3 max-w-prose">{{ franchise ? t("accounting.franchiseLead") : t("accounting.vatLead") }}</p>
      <p v-if="loading" class="text-sm text-slate-500">{{ t("common.loading") }}</p>
      <p v-else-if="!periods.length" class="text-sm text-slate-500">{{ t("accounting.empty") }}</p>
      <div v-else class="-mx-1 overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-slate-500">
              <th class="font-medium pb-1 px-1">{{ t("accounting.periodCol") }}</th>
              <th class="font-medium pb-1 px-1 text-right">{{ t("accounting.invoicedHt") }}</th>
              <th class="font-medium pb-1 px-1 text-right">{{ t("accounting.collectedGoods") }}</th>
              <th class="font-medium pb-1 px-1 text-right">{{ t("accounting.collectedServices") }}</th>
              <template v-if="!franchise">
                <th v-for="r in rates" :key="r" class="font-medium pb-1 px-1 text-right">{{ t("accounting.vatRate", { rate: r }) }}</th>
                <th class="font-medium pb-1 px-1 text-right">{{ t("accounting.vatDue") }}</th>
              </template>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in periods" :key="p.key" class="border-t border-slate-100">
              <td class="py-1.5 px-1 capitalize">{{ periodLabel(p) }}</td>
              <td class="py-1.5 px-1 text-right tabular-nums">{{ money(p.invoiced_ht) }}</td>
              <td class="py-1.5 px-1 text-right tabular-nums">{{ money(p.collected_goods) }}</td>
              <td class="py-1.5 px-1 text-right tabular-nums">{{ money(p.collected_services) }}</td>
              <template v-if="!franchise">
                <td v-for="r in rates" :key="r" class="py-1.5 px-1 text-right tabular-nums">
                  <span v-if="vatOf(p, r)" :title="t('accounting.base', { amount: money(vatOf(p, r)!.base) })">{{ money(vatOf(p, r)!.vat) }}</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="py-1.5 px-1 text-right tabular-nums font-medium">{{ money(totalVat(p)) }}</td>
              </template>
            </tr>
          </tbody>
          <tfoot>
            <tr class="border-t-2 border-slate-300 font-semibold">
              <td class="py-1.5 px-1">{{ t("accounting.total") }}</td>
              <td class="py-1.5 px-1 text-right tabular-nums">{{ money(sum((p) => p.invoiced_ht)) }}</td>
              <td class="py-1.5 px-1 text-right tabular-nums">{{ money(sum((p) => p.collected_goods)) }}</td>
              <td class="py-1.5 px-1 text-right tabular-nums">{{ money(sum((p) => p.collected_services)) }}</td>
              <template v-if="!franchise">
                <td v-for="r in rates" :key="r" class="py-1.5 px-1 text-right tabular-nums">{{ money(sum((p) => vatOf(p, r)?.vat ?? 0)) }}</td>
                <td class="py-1.5 px-1 text-right tabular-nums">{{ money(sum(totalVat)) }}</td>
              </template>
            </tr>
          </tfoot>
        </table>
      </div>
      <ul class="mt-4 text-xs text-slate-500 space-y-1 max-w-prose list-disc pl-4">
        <li>{{ t("accounting.noteCollected") }}</li>
        <li v-if="!franchise">{{ t("accounting.noteVat") }}</li>
        <li v-if="!franchise">{{ t("accounting.noteMixed") }}</li>
        <li>{{ t("accounting.noteAccountant") }}</li>
      </ul>
    </section>
  </div>
</template>
