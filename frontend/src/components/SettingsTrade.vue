<script setup lang="ts">
import { onMounted, ref } from "vue";

import { loadStages, setStages, useStages } from "@/composables/useStages";
import { currentTrade, useI18n, type Trade } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

/** The workshop's trade (vocabulary, default stages, tools shown) and its own stages. */
const { t } = useI18n();
const store = useAppStore();
const trade = currentTrade();
const { stages, stageLabel } = useStages();

interface Row { key: string | null; label: string; builtin: boolean; used: number }
const rows = ref<Row[]>([]);
const msg = ref("");
const error = ref("");

function fill() {
  rows.value = stages.value.map((s) => ({ key: s.key, label: s.label ?? stageLabel(s.key), builtin: !s.label, used: s.used }));
}
onMounted(async () => {
  await loadStages(true);
  fill();
});

async function chooseTrade(next: Trade) {
  error.value = "";
  try {
    await store.updateShopSettings({ trade: next });
    await loadStages(true);
    fill();
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

function move(i: number, d: number) {
  const j = i + d;
  if (j < 0 || j >= rows.value.length) return;
  const r = rows.value.splice(i, 1)[0];
  rows.value.splice(j, 0, r);
}

async function save() {
  msg.value = "";
  error.value = "";
  try {
    // a built-in stage left with its translated name stays built-in (it follows the language)
    const body = rows.value.map((r) => ({ key: r.key, label: r.builtin && r.key && r.label === stageLabel(r.key) ? null : r.label.trim() || null }));
    setStages(await store.saveStages(body));
    fill();
    msg.value = t("settings.shop.saved");
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

async function reset() {
  error.value = "";
  try {
    setStages(await store.resetStages());
    fill();
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}
</script>

<template>
  <section class="sheet p-5" aria-labelledby="trade-title">
    <h2 id="trade-title" class="sheet-title">{{ t("trade.title") }}</h2>
    <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("trade.hint") }}</p>
    <div class="mt-3 flex gap-2" role="radiogroup" :aria-label="t('trade.title')">
      <button v-for="tr in (['knifemaker', 'blacksmith'] as const)" :key="tr" role="radio" :aria-checked="trade === tr"
              class="btn btn-sm border" :class="trade === tr ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
              @click="chooseTrade(tr)">{{ t(`trade.${tr}`) }}</button>
    </div>

    <h3 class="mt-5 text-sm font-semibold text-slate-800">{{ t("trade.stages") }}</h3>
    <p class="text-xs text-slate-500 mt-1 max-w-prose">{{ t("trade.stagesHint") }}</p>
    <ol class="mt-2 space-y-1.5">
      <li v-for="(r, i) in rows" :key="i" class="flex items-center gap-1.5">
        <span class="w-5 text-right text-xs tabular-nums text-slate-400">{{ i + 1 }}</span>
        <input v-model="r.label" maxlength="60" class="input-sm flex-1" :aria-label="t('trade.stageName', { n: i + 1 })" />
        <span v-if="r.used" class="tag tag-neutral text-xs" :title="t('trade.usedHint')">{{ r.used }}</span>
        <button type="button" class="p-1 rounded text-slate-500 hover:bg-slate-100 disabled:opacity-30" :disabled="i === 0" :aria-label="t('trade.up')" @click="move(i, -1)">↑</button>
        <button type="button" class="p-1 rounded text-slate-500 hover:bg-slate-100 disabled:opacity-30" :disabled="i === rows.length - 1" :aria-label="t('trade.down')" @click="move(i, 1)">↓</button>
        <button type="button" class="p-1 rounded text-slate-500 hover:text-red-700 hover:bg-slate-100 disabled:opacity-30" :disabled="r.used > 0 || rows.length <= 2" :aria-label="t('common.delete')" @click="rows.splice(i, 1)">×</button>
      </li>
    </ol>
    <div class="mt-3 flex flex-wrap items-center gap-3">
      <button type="button" class="link-action" :disabled="rows.length >= 16" @click="rows.push({ key: null, label: '', builtin: false, used: 0 })">+ {{ t("trade.addStage") }}</button>
      <button type="button" class="btn btn-primary btn-sm" @click="save">{{ t("common.save") }}</button>
      <button type="button" class="link-action" @click="reset">{{ t("trade.reset") }}</button>
      <span v-if="msg" class="text-sm text-emerald-700" role="status">{{ msg }}</span>
    </div>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-700">{{ error }}</p>
  </section>
</template>
