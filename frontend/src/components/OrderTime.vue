<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { useStages } from "@/composables/useStages";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { TimeSummary } from "@/types";

/** Time spent on an order, against what its models plan, and what it costs at the shop rate. */
const props = defineProps<{ orderId: number; stage: string }>();
const { t, money, locale } = useI18n();
const store = useAppStore();
const { stages, stageLabel } = useStages();

const summary = ref<TimeSummary | null>(null);
const today = () => new Date().toISOString().slice(0, 10);
const form = reactive({ worked_on: today(), hours: 1, minutes: 0, stage: props.stage, note: "" });
const error = ref("");

onMounted(async () => {
  try {
    summary.value = await store.orderTime(props.orderId);
  } catch (err) {
    error.value = errorMessage(err, t);
  }
});

const hm = (m: number) => `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
const share = computed(() => (summary.value && summary.value.planned_minutes ? summary.value.spent_minutes / summary.value.planned_minutes : 0));
const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale.value === "fr" ? "fr-FR" : "en-GB");

async function add() {
  const minutes = Math.round((Number(form.hours) || 0) * 60 + (Number(form.minutes) || 0));
  if (minutes <= 0) {
    error.value = t("time.invalid");
    return;
  }
  error.value = "";
  try {
    summary.value = await store.addTime(props.orderId, { worked_on: form.worked_on, minutes, stage: form.stage || null, note: form.note.trim() || null });
    form.note = "";
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

async function remove(id: number) {
  try {
    summary.value = await store.deleteTime(props.orderId, id);
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}
</script>

<template>
  <section class="sheet p-4" aria-labelledby="time-title">
    <h2 id="time-title" class="sheet-title mb-2">{{ t("time.title") }}</h2>
    <template v-if="summary">
      <dl class="grid grid-cols-3 gap-3 text-sm">
        <div><dt class="text-slate-500">{{ t("time.spent") }}</dt><dd class="font-medium tabular-nums">{{ hm(summary.spent_minutes) }}</dd></div>
        <div><dt class="text-slate-500">{{ t("time.planned") }}</dt><dd class="font-medium tabular-nums">{{ summary.planned_minutes ? hm(summary.planned_minutes) : "—" }}</dd></div>
        <div><dt class="text-slate-500">{{ t("time.cost") }}</dt><dd class="font-medium tabular-nums">{{ money(summary.spent_cost) }}</dd></div>
      </dl>
      <div v-if="summary.planned_minutes" class="mt-2 h-2 rounded-full bg-slate-200 overflow-hidden" role="img" :aria-label="t('time.progress', { pct: Math.round(share * 100) })">
        <div class="h-full rounded-full" :class="share > 1 ? 'bg-red-600' : 'bg-accent-600'" :style="{ width: `${Math.min(100, share * 100)}%` }"></div>
      </div>
      <p v-if="summary.planned_minutes && share > 1" class="mt-1 text-xs text-red-700">{{ t("time.over", { over: hm(summary.spent_minutes - summary.planned_minutes) }) }}</p>

      <ul v-if="summary.entries.length" class="mt-3 divide-y divide-slate-100 text-sm">
        <li v-for="e in [...summary.entries].reverse()" :key="e.id" class="py-1.5 flex items-baseline gap-3">
          <span class="tabular-nums text-slate-500 w-24 shrink-0">{{ fmtDate(e.worked_on) }}</span>
          <span class="tabular-nums font-medium w-16 shrink-0">{{ hm(e.minutes) }}</span>
          <span class="text-slate-600 min-w-0 truncate">{{ e.stage ? stageLabel(e.stage) : "" }}{{ e.note ? ` · ${e.note}` : "" }}</span>
          <button class="link-danger text-xs ml-auto" :aria-label="t('common.delete')" @click="remove(e.id)">{{ t("common.delete") }}</button>
        </li>
      </ul>

      <form class="mt-3 grid gap-2 grid-cols-2 items-end" @submit.prevent="add">
        <label class="block"><span class="field-label">{{ t("time.date") }}</span><input v-model="form.worked_on" type="date" required class="input-sm w-full" /></label>
        <label class="block"><span class="field-label">{{ t("time.duration") }}</span>
          <span class="flex items-center gap-1"><input v-model.number="form.hours" type="number" min="0" max="24" class="input-sm w-14 text-right" :aria-label="t('time.hours')" /> h
            <input v-model.number="form.minutes" type="number" min="0" max="59" step="5" class="input-sm w-14 text-right" :aria-label="t('time.minutes')" /></span>
        </label>
        <label class="block"><span class="field-label">{{ t("time.stage") }}</span>
          <select v-model="form.stage" class="input-sm w-full">
            <option value="">—</option>
            <option v-for="s in stages" :key="s.key" :value="s.key">{{ stageLabel(s.key) }}</option>
          </select>
        </label>
        <label class="block"><span class="field-label">{{ t("time.note") }}</span><input v-model="form.note" maxlength="300" class="input-sm w-full" /></label>
        <div class="col-span-2"><button type="submit" class="btn btn-primary btn-sm">{{ t("time.add") }}</button></div>
      </form>
    </template>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-700">{{ error }}</p>
  </section>
</template>
