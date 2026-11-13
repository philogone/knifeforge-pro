<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import BackupRestore from "@/components/BackupRestore.vue";
import { errorMessage } from "@/i18n/apiErrors";
import { currentTrade, useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";

const { t } = useI18n();
const store = useAppStore();
const trade = currentTrade();
const router = useRouter();

const step = ref(1);
const STEPS = 3;
const busy = ref(false);
const error = ref("");
const workshop = reactive({ workshop_name: "", workshop_contact: "", workshop_logo: "" });
const demoOn = ref(false);

onMounted(async () => {
  const s = await store.fetchShopSettings();
  workshop.workshop_name = s.workshop_name ?? "";
  workshop.workshop_contact = s.workshop_contact ?? "";
  workshop.workshop_logo = s.workshop_logo ?? "";
  demoOn.value = (await store.mockDataStatus()).enabled;
});

function onLogo(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (!["image/png", "image/jpeg", "image/svg+xml"].includes(file.type) || file.size > 250_000) {
    error.value = t("settings.workshop.logoType");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => (workshop.workshop_logo = String(reader.result));
  reader.readAsDataURL(file);
}

async function run(action: () => Promise<unknown>, next?: number) {
  busy.value = true;
  error.value = "";
  try {
    await action();
    if (next) step.value = next;
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

const saveWorkshop = () => run(() => store.updateShopSettings({ ...workshop }), 2);
const keepDemo = () => run(async () => undefined, 3);
const clearDemo = () =>
  run(async () => {
    await store.clearMockData();
    demoOn.value = false;
  }, 3);

async function restored() {
  // the backup brings its own settings: the workshop is set up, go straight to it
  await run(() => store.updateShopSettings({ onboarding_done: true }));
  if (!error.value) router.push("/");
}

async function finish(to: string) {
  await run(() => store.updateShopSettings({ onboarding_done: true }));
  if (!error.value) router.push(to);
}
</script>

<template>
  <div class="page max-w-2xl">
    <p class="text-sm text-slate-500 tabular-nums">{{ t("welcome.step", { n: step, total: STEPS }) }}</p>
    <div class="mt-2 mb-6 h-1 rounded-full bg-slate-200 overflow-hidden" aria-hidden="true">
      <div class="h-full bg-accent-600 transition-all duration-300" :style="{ width: `${(step / STEPS) * 100}%` }"></div>
    </div>

    <!-- 1. the workshop -->
    <section v-if="step === 1" class="sheet p-6">
      <h1 class="page-title">{{ t("welcome.title") }}</h1>
      <p class="page-lead">{{ t("welcome.lead") }}</p>
      <div class="mt-6 space-y-4">
        <div role="radiogroup" :aria-label="t('trade.title')">
          <span class="field-label">{{ t("welcome.trade") }}</span>
          <div class="flex gap-2">
            <button v-for="tr in (['knifemaker', 'blacksmith'] as const)" :key="tr" type="button" role="radio" :aria-checked="trade === tr"
                    class="btn btn-sm border" :class="trade === tr ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
                    @click="store.updateShopSettings({ trade: tr })">{{ t(`trade.${tr}`) }}</button>
          </div>
        </div>
        <label class="block">
          <span class="field-label">{{ t("settings.workshop.name") }}</span>
          <input v-model="workshop.workshop_name" v-focus maxlength="120" autocomplete="organization" class="input w-full" />
        </label>
        <label class="block">
          <span class="field-label">{{ t("settings.workshop.contact") }}</span>
          <input v-model="workshop.workshop_contact" maxlength="200" :placeholder="t('settings.workshop.contactExample')" class="input w-full" />
        </label>
        <div class="flex items-center gap-4">
          <div class="w-32 h-16 rounded-lg border border-dashed border-slate-300 plate flex items-center justify-center overflow-hidden">
            <img v-if="workshop.workshop_logo" :src="workshop.workshop_logo" :alt="t('settings.workshop.logoAlt')" class="max-w-full max-h-full object-contain" />
            <span v-else class="text-xs text-[#6f6a60]">{{ t("settings.workshop.noLogo") }}</span>
          </div>
          <label class="link-action cursor-pointer">
            {{ workshop.workshop_logo ? t("settings.workshop.replaceLogo") : t("settings.workshop.addLogo") }}
            <input type="file" accept="image/png,image/jpeg,image/svg+xml" class="sr-only" @change="onLogo" />
          </label>
        </div>
        <p class="sheet-hint">{{ t("welcome.workshopHint") }}</p>
      </div>
      <div class="mt-6 flex items-center gap-3">
        <button class="btn btn-primary" :disabled="busy" @click="saveWorkshop">{{ t("welcome.next") }}</button>
        <button class="link-action" @click="step = 2">{{ t("welcome.later") }}</button>
      </div>
    </section>

    <!-- already a KnifeForge user: new computer, reinstallation, Docker -> installer -->
    <section v-if="step === 1" class="sheet p-6 mt-4">
      <h2 class="sheet-title">{{ t("welcome.restoreTitle") }}</h2>
      <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("welcome.restoreLead") }}</p>
      <div class="mt-4"><BackupRestore :label="t('welcome.restorePick')" @restored="restored" /></div>
    </section>

    <!-- 2. demo data -->
    <section v-else-if="step === 2" class="sheet p-6">
      <h1 class="page-title">{{ t("welcome.demoTitle") }}</h1>
      <p class="page-lead">{{ demoOn ? t("welcome.demoOn") : t("welcome.demoOff") }}</p>
      <div class="mt-6 flex flex-wrap items-center gap-3">
        <template v-if="demoOn">
          <button class="btn btn-primary" :disabled="busy" @click="clearDemo">{{ t("welcome.demoClear") }}</button>
          <button class="btn btn-outline" :disabled="busy" @click="keepDemo">{{ t("welcome.demoKeep") }}</button>
        </template>
        <button v-else class="btn btn-primary" @click="step = 3">{{ t("welcome.next") }}</button>
        <button class="link-action" @click="step = 1">{{ t("welcome.back") }}</button>
      </div>
    </section>

    <!-- 3. where to start -->
    <section v-else class="sheet p-6">
      <h1 class="page-title">{{ t("welcome.doneTitle") }}</h1>
      <p class="page-lead">{{ t("welcome.doneLead") }}</p>
      <ol class="mt-6 space-y-3">
        <li v-for="(s, i) in [
          { to: '/materials', key: 'welcome.start.materials' },
          { to: '/knife-models', key: 'welcome.start.models' },
          { to: '/designs', key: 'welcome.start.designs' },
          { to: '/orders', key: 'welcome.start.orders' },
        ]" :key="s.to">
          <button class="w-full text-left sheet px-4 py-3 flex items-center gap-3 hover:border-slate-300 transition-colors" :disabled="busy" @click="finish(s.to)">
            <span class="w-6 h-6 rounded-full bg-accent-600 text-white text-xs flex items-center justify-center tabular-nums">{{ i + 1 }}</span>
            <span class="text-sm text-slate-800">{{ t(s.key) }}</span>
          </button>
        </li>
      </ol>
      <div class="mt-6">
        <button class="link-action" @click="step = 2">{{ t("welcome.back") }}</button>
      </div>
    </section>

    <p v-if="error" class="mt-4 text-sm text-red-700" role="alert">{{ error }}</p>
  </div>
</template>
