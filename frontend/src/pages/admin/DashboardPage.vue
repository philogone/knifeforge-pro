<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { errorMessage } from "@/i18n/apiErrors";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { Dashboard, OrderStage, OrderStatus } from "@/types";

const { t, locale, money, qty } = useI18n();
const store = useAppStore();
const data = ref<Dashboard | null>(null);
const workshop = ref<string | null>(null);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    const [dash, shop] = await Promise.all([store.fetchDashboard(), store.fetchShopSettings()]);
    data.value = dash;
    workshop.value = shop.workshop_name;
  } catch (err) {
    error.value = errorMessage(err, t);
  }
  try {
    backupReminder.value = (await store.backupStatus()).remind;
  } catch {
    // no reminder rather than an error on the home page
  }
});
// desktop build: no backup (automatic or downloaded) for a week
const backupReminder = ref(false);

const intlLocale = computed(() => (locale.value === "fr" ? "fr-FR" : "en-GB"));
function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
const todayLabel = computed(() => {
  if (!data.value) return "";
  const s = parseDay(data.value.today).toLocaleDateString(intlLocale.value, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  return s.charAt(0).toUpperCase() + s.slice(1);
});
const shortDate = (iso: string) => parseDay(iso).toLocaleDateString(intlLocale.value, { day: "numeric", month: "short" });

// ---- orders by status: a donut in a fixed order (the palette was validated in this order)
const STATUS_ORDER: OrderStatus[] = ["draft", "confirmed", "cancelled", "completed"];
const R = 52;
const CIRC = 2 * Math.PI * R;
const GAP = 2; // px of surface between segments
const statusTotal = computed(() => (data.value ? STATUS_ORDER.reduce((s, k) => s + data.value!.orders.by_status[k], 0) : 0));
const donut = computed(() => {
  if (!data.value || !statusTotal.value) return [];
  const present = STATUS_ORDER.filter((k) => data.value!.orders.by_status[k] > 0);
  let offset = 0;
  return present.map((k) => {
    const n = data.value!.orders.by_status[k];
    const len = (n / statusTotal.value) * CIRC;
    const seg = { key: k, n, dash: `${Math.max(len - (present.length > 1 ? GAP : 0), 0.5)} ${CIRC}`, offset: -offset };
    offset += len;
    return seg;
  });
});

// ---- active orders per workshop stage
const STAGES: OrderStage[] = ["todo", "forging", "heat_treatment", "grinding", "handle", "finishing", "ready", "delivered"];
const stageMax = computed(() => Math.max(1, ...STAGES.map((s) => data.value?.orders.by_stage[s] ?? 0)));

// ---- draft feasibility: a half-circle gauge
const draftsTotal = computed(() => (data.value ? data.value.orders.drafts_feasible + data.value.orders.drafts_short : 0));
const feasibleShare = computed(() => (draftsTotal.value ? data.value!.orders.drafts_feasible / draftsTotal.value : 0));
const GAUGE_LEN = Math.PI * 70; // half circle, r = 70
const gaugeDash = computed(() => `${feasibleShare.value * GAUGE_LEN} ${GAUGE_LEN}`);

// ---- invoiced per month (excl. tax), last 6 months
const monthMax = computed(() => Math.max(1, ...(data.value?.finance.monthly.map((m) => m.amount_ht) ?? [0])));
const monthLabel = (ym: string) => {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(intlLocale.value, { month: "short" }).replace(".", "");
};
const BAR_H = 130;
const bars = computed(() =>
  (data.value?.finance.monthly ?? []).map((m, i) => {
    const h = m.amount_ht > 0 ? Math.max(3, (m.amount_ht / monthMax.value) * BAR_H) : 0;
    return { ...m, x: 12 + i * 66, h, y: 20 + BAR_H - h };
  }),
);

// ---- pipeline: cost and margin share of the sale price of orders in progress
const pipelineSplit = computed(() => {
  const f = data.value?.finance;
  if (!f || f.pipeline_revenue <= 0) return null;
  const cost = Math.min(1, Math.max(0, f.pipeline_cost / f.pipeline_revenue));
  return { cost: cost * 100, margin: (1 - cost) * 100, rate: Math.round((f.pipeline_margin / f.pipeline_revenue) * 100) };
});

// ---- stock: gauge scaled to twice the alert threshold (the threshold sits at mid-track)
const STOCK_ROWS = 8;
const stockRows = computed(() => (data.value?.stock.materials ?? []).slice(0, STOCK_ROWS));
const gaugeFill = (q: number, threshold: number) => (threshold > 0 ? Math.min(100, (q / (threshold * 2)) * 100) : 0);
</script>

<template>
  <div class="page max-w-[1600px]">
    <p v-if="error" role="alert" class="sheet p-6 text-sm text-red-700">{{ error }}</p>
    <p v-if="backupReminder" class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900" role="status">
      {{ t("dashboard.backupReminder") }}
      <router-link to="/settings" class="ml-1 underline underline-offset-2">{{ t("dashboard.backupNow") }}</router-link>
    </p>

    <template v-if="data">
      <header class="page-head">
        <div>
          <p class="text-sm text-slate-500">{{ workshop || t("dash.title") }}</p>
          <h1 class="page-title">{{ todayLabel }}</h1>
        </div>
        <div class="flex gap-2">
          <router-link to="/orders" class="btn btn-outline">{{ t("dash.newOrder") }}</router-link>
          <router-link to="/designs" class="btn btn-outline">{{ t("dash.openDesigns") }}</router-link>
        </div>
      </header>

      <!-- headline figures -->
      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0" :aria-label="t('dash.keyFigures')">
        <router-link to="/orders" class="sheet p-4 dash-tile">
          <span class="dash-label">{{ t("dash.activeOrders") }}</span>
          <span class="dash-figure">{{ data.orders.active }}</span>
          <span class="dash-sub">
            <span v-if="data.orders.late" class="text-[color:var(--viz-low)] font-medium">{{ t("dash.late", { n: data.orders.late }) }}</span>
            <span v-if="data.orders.late"> · </span>{{ t("dash.dueWeek", { n: data.orders.due_this_week }) }}
          </span>
        </router-link>

        <router-link to="/production" class="sheet p-4 dash-tile">
          <span class="dash-label">{{ t("dash.potentialMargin") }}</span>
          <span class="dash-figure">{{ money(data.finance.pipeline_margin) }}</span>
          <span class="dash-sub">{{ t("dash.onSales", { amount: money(data.finance.pipeline_revenue) }) }}</span>
          <span v-if="data.finance.unpriced_lines" class="dash-sub text-[color:var(--viz-low)]">{{ t("dash.unpriced", { n: data.finance.unpriced_lines }) }}</span>
        </router-link>

        <router-link to="/documents" class="sheet p-4 dash-tile">
          <span class="dash-label">{{ t("dash.invoicedMonth") }}</span>
          <span class="dash-figure">{{ money(data.finance.invoiced_month_ht) }}</span>
          <span class="dash-sub">{{ t("dash.invoicedYear", { amount: money(data.finance.invoiced_year_ht) }) }}</span>
        </router-link>

        <router-link to="/documents" class="sheet p-4 dash-tile">
          <span class="dash-label">{{ t("dash.toCollect") }}</span>
          <span class="dash-figure">{{ money(data.finance.unpaid_ttc) }}</span>
          <span class="dash-sub">
            {{ t("dash.unpaidCount", { n: data.finance.unpaid_count }) }}<template v-if="data.finance.unpaid_overdue"> · <span class="text-[color:var(--viz-low)] font-medium">{{ t("dash.overdue", { n: data.finance.unpaid_overdue }) }}</span></template>
          </span>
          <span v-if="data.finance.quotes_pending_count" class="dash-sub">{{ t("dash.quotesPending", { n: data.finance.quotes_pending_count, amount: money(data.finance.quotes_pending_ht) }) }}</span>
        </router-link>
      </section>

      <div class="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3 items-start [&>*]:min-w-0">
        <!-- orders by status -->
        <section class="sheet p-4" aria-labelledby="dash-status">
          <h2 id="dash-status" class="sheet-title">{{ t("dash.ordersByStatus") }}</h2>
          <div class="mt-3 flex items-center gap-6">
            <svg width="140" height="140" viewBox="0 0 140 140" role="img" :aria-label="t('dash.ordersByStatus')" class="shrink-0">
              <circle cx="70" cy="70" :r="R" fill="none" stroke="var(--viz-track)" stroke-width="16" />
              <g transform="rotate(-90 70 70)">
                <circle
                  v-for="seg in donut"
                  :key="seg.key"
                  cx="70" cy="70" :r="R" fill="none" stroke-width="16"
                  :stroke="`var(--viz-${seg.key})`"
                  :stroke-dasharray="seg.dash"
                  :stroke-dashoffset="seg.offset"
                >
                  <title>{{ t(`orders.status.${seg.key}`) }} : {{ seg.n }}</title>
                </circle>
              </g>
              <text x="70" y="68" text-anchor="middle" class="dash-donut-figure">{{ statusTotal }}</text>
              <text x="70" y="86" text-anchor="middle" class="dash-donut-caption">{{ t("dash.orders", { n: statusTotal }) }}</text>
            </svg>
            <ul class="space-y-2 text-sm min-w-0 flex-1">
              <li v-for="k in STATUS_ORDER" :key="k" class="flex items-center gap-2">
                <span class="h-2.5 w-2.5 rounded-sm shrink-0" :style="{ background: `var(--viz-${k})` }" aria-hidden="true"></span>
                <span class="text-slate-700 first-letter:uppercase">{{ t(`orders.status.${k}`) }}</span>
                <span class="ml-auto tabular-nums font-medium text-slate-900">{{ data.orders.by_status[k] }}</span>
              </li>
            </ul>
          </div>
        </section>

        <!-- active orders per workshop stage -->
        <section class="sheet p-4" aria-labelledby="dash-stage">
          <h2 id="dash-stage" class="sheet-title">{{ t("dash.onTheBench") }}</h2>
          <p class="sheet-hint mt-1">{{ t("dash.onTheBenchHint") }}</p>
          <ul class="mt-3 space-y-1.5">
            <li v-for="s in STAGES" :key="s" class="grid grid-cols-[9rem_1fr_2rem] items-center gap-3 text-sm">
              <span class="text-slate-700 truncate">{{ t(`orders.stage.${s}`) }}</span>
              <span class="h-2 rounded-full bg-[color:var(--viz-track)] overflow-hidden" aria-hidden="true">
                <span class="block h-full rounded-full bg-[color:var(--viz-mark)]" :style="{ width: `${(data.orders.by_stage[s] / stageMax) * 100}%` }"></span>
              </span>
              <span class="text-right tabular-nums" :class="data.orders.by_stage[s] ? 'text-slate-900 font-medium' : 'text-slate-400'">{{ data.orders.by_stage[s] }}</span>
            </li>
          </ul>
        </section>

        <!-- promised dates -->
        <section class="sheet p-4" aria-labelledby="dash-due">
          <h2 id="dash-due" class="sheet-title">{{ t("dash.dueDates") }}</h2>
          <p v-if="!data.orders.upcoming.length" class="mt-3 text-sm text-slate-500">{{ t("dash.noDueDates") }}</p>
          <ul v-else class="mt-2 divide-y divide-slate-100">
            <li v-for="o in data.orders.upcoming" :key="o.order_id">
              <router-link :to="`/orders/${o.order_id}`" class="flex items-center gap-3 py-2 text-sm hover:bg-slate-50 -mx-2 px-2 rounded">
                <span class="w-16 shrink-0 tabular-nums" :class="o.late ? 'text-[color:var(--viz-low)] font-medium' : 'text-slate-600'">{{ shortDate(o.due_date) }}</span>
                <span class="text-slate-900 truncate min-w-0">{{ o.customer_name }}</span>
                <span class="ml-auto text-xs text-slate-500 whitespace-nowrap">{{ t(`orders.stage.${o.stage}`) }}</span>
                <span v-if="o.late" class="tag tag-danger">{{ t("dash.lateTag") }}</span>
              </router-link>
            </li>
          </ul>
        </section>

        <!-- invoiced per month -->
        <section class="sheet p-4" aria-labelledby="dash-months">
          <h2 id="dash-months" class="sheet-title">{{ t("dash.invoiced6") }}</h2>
          <p class="sheet-hint mt-1">{{ t("dash.invoiced6Hint") }}</p>
          <p v-if="!data.finance.monthly.some((m) => m.amount_ht)" class="mt-3 text-sm text-slate-500">{{ t("dash.noInvoices") }}</p>
          <svg v-else viewBox="0 0 420 176" class="mt-3 w-full max-w-[420px]" role="img" :aria-label="t('dash.invoiced6')">
            <line x1="4" x2="416" :y1="20 + BAR_H" :y2="20 + BAR_H" stroke="var(--viz-track)" stroke-width="1" />
            <g v-for="b in bars" :key="b.month">
              <rect :x="b.x" y="20" width="56" :height="BAR_H" fill="transparent">
                <title>{{ monthLabel(b.month) }} : {{ money(b.amount_ht) }}</title>
              </rect>
              <rect v-if="b.h" :x="b.x + 10" :y="b.y" width="36" :height="b.h" rx="3" fill="var(--viz-mark)" pointer-events="none" />
              <text :x="b.x + 28" :y="20 + BAR_H + 18" text-anchor="middle" class="dash-axis">{{ monthLabel(b.month) }}</text>
            </g>
            <text
              v-if="bars.length && bars[bars.length - 1].amount_ht"
              :x="bars[bars.length - 1].x + 28" :y="Math.max(bars[bars.length - 1].y - 6, 12)"
              text-anchor="middle" class="dash-axis dash-axis-strong"
            >{{ money(bars[bars.length - 1].amount_ht) }}</text>
          </svg>
        </section>

        <!-- stock levels -->
        <section class="sheet p-4" aria-labelledby="dash-stock">
          <div class="flex items-baseline justify-between gap-3">
            <h2 id="dash-stock" class="sheet-title">{{ t("dash.stock") }}</h2>
            <router-link to="/materials" class="link-action text-sm">{{ t("dash.allMaterials") }}</router-link>
          </div>
          <p class="sheet-hint mt-1">
            {{ t("dash.stockValue", { amount: money(data.stock.total_value) }) }}<template v-if="data.stock.low_count"> · <span class="text-[color:var(--viz-low)] font-medium">{{ t("dash.lowCount", { n: data.stock.low_count }) }}</span></template>
          </p>
          <p v-if="!stockRows.length" class="mt-3 text-sm text-slate-500">{{ t("dash.noMaterials") }}</p>
          <ul v-else class="mt-3 space-y-2.5">
            <li v-for="m in stockRows" :key="m.material_id" class="text-sm">
              <div class="flex items-baseline gap-2">
                <span class="text-slate-800 truncate min-w-0">{{ m.name }}</span>
                <span v-if="m.low" class="tag tag-danger">{{ t("dash.lowTag") }}</span>
                <span class="ml-auto tabular-nums text-slate-600 whitespace-nowrap">{{ qty(m.quantity, m.unit) }}</span>
              </div>
              <div v-if="m.threshold > 0" class="relative mt-1 h-1.5 rounded-full bg-[color:var(--viz-track)]" :title="t('dash.threshold', { q: qty(m.threshold, m.unit) })">
                <span class="block h-full rounded-full" :style="{ width: `${gaugeFill(m.quantity, m.threshold)}%`, background: m.low ? 'var(--viz-low)' : 'var(--viz-mark)' }"></span>
                <span class="absolute top-[-3px] bottom-[-3px] left-1/2 w-px bg-slate-500" aria-hidden="true"></span>
              </div>
              <p v-else class="mt-0.5 text-xs text-slate-400">{{ t("dash.noThreshold") }}</p>
            </li>
          </ul>
          <p v-if="data.stock.materials.length" class="mt-3 text-xs text-slate-500">{{ t("dash.gaugeHint") }}</p>
        </section>

        <!-- feasibility and pipeline -->
        <section class="sheet p-4" aria-labelledby="dash-feasible">
          <h2 id="dash-feasible" class="sheet-title">{{ t("dash.feasibility") }}</h2>
          <p v-if="!draftsTotal" class="mt-3 text-sm text-slate-500">{{ t("dash.noDrafts") }}</p>
          <div v-else class="mt-2 flex items-center gap-5">
            <svg width="170" height="98" viewBox="0 0 170 98" role="img" :aria-label="t('dash.feasibleOf', { n: data.orders.drafts_feasible, total: draftsTotal })" class="shrink-0">
              <path d="M 15 85 A 70 70 0 0 1 155 85" fill="none" stroke="var(--viz-track)" stroke-width="12" stroke-linecap="round" />
              <path v-if="feasibleShare > 0" d="M 15 85 A 70 70 0 0 1 155 85" fill="none" stroke="var(--viz-mark)" stroke-width="12" stroke-linecap="round" :stroke-dasharray="gaugeDash" />
              <text x="85" y="78" text-anchor="middle" class="dash-donut-figure">{{ data.orders.drafts_feasible }}/{{ draftsTotal }}</text>
            </svg>
            <div class="text-sm space-y-1">
              <p class="text-slate-800">{{ t("dash.feasibleOf", { n: data.orders.drafts_feasible, total: draftsTotal }) }}</p>
              <p v-if="data.orders.drafts_short" class="text-[color:var(--viz-low)]">{{ t("dash.shortDrafts", { n: data.orders.drafts_short }) }}</p>
              <router-link to="/production" class="link-action">{{ t("dash.seeProduction") }}</router-link>
            </div>
          </div>

          <div class="mt-5 pt-4 border-t border-slate-100">
            <h3 class="text-sm font-medium text-slate-900">{{ t("dash.pipeline") }}</h3>
            <p v-if="!pipelineSplit" class="mt-2 text-sm text-slate-500">{{ t("dash.noPipeline") }}</p>
            <template v-else>
              <div class="mt-2 flex h-3 gap-0.5" role="img" :aria-label="t('dash.pipelineAria', { cost: money(data.finance.pipeline_cost), margin: money(data.finance.pipeline_margin) })">
                <span class="h-full rounded-l-full bg-slate-400" :style="{ width: `${pipelineSplit.cost}%` }" :title="`${t('dash.cost')} : ${money(data.finance.pipeline_cost)}`"></span>
                <span class="h-full rounded-r-full bg-[color:var(--viz-mark)]" :style="{ width: `${pipelineSplit.margin}%` }" :title="`${t('dash.margin')} : ${money(data.finance.pipeline_margin)}`"></span>
              </div>
              <div class="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
                <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-slate-400" aria-hidden="true"></span>{{ t("dash.cost") }} <span class="tabular-nums text-slate-900">{{ money(data.finance.pipeline_cost) }}</span></span>
                <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-[color:var(--viz-mark)]" aria-hidden="true"></span>{{ t("dash.margin") }} <span class="tabular-nums text-slate-900">{{ money(data.finance.pipeline_margin) }}</span> <span class="text-slate-500">({{ pipelineSplit.rate }} %)</span></span>
              </div>
            </template>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dash-tile {
  @apply flex flex-col gap-1 transition-colors hover:border-slate-300;
}
.dash-label {
  @apply text-sm text-slate-600;
}
.dash-figure {
  @apply text-[1.75rem] leading-tight font-semibold tracking-tight tabular-nums text-slate-900;
}
.dash-sub {
  @apply text-xs text-slate-500;
}
.dash-donut-figure {
  font-size: 22px;
  font-weight: 600;
  fill: rgb(var(--slate-900));
  font-variant-numeric: tabular-nums;
}
.dash-donut-caption {
  font-size: 11px;
  fill: rgb(var(--slate-500));
}
.dash-axis {
  font-size: 11px;
  fill: rgb(var(--slate-500));
}
.dash-axis-strong {
  fill: rgb(var(--slate-900));
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>
