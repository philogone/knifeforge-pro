<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { type Locale, useI18n } from "@/i18n";
import { type ThemeChoice, useTheme } from "@/composables/useTheme";
import { CARD_HEIGHT_MM, CARD_WIDTH_MM, isScreenCalibrated, saveScreenCalibration, screenPxPerMm } from "@/editor/screenScale";
import { errorMessage } from "@/i18n/apiErrors";
import BackupRestore from "@/components/BackupRestore.vue";
import SettingsAccounting from "@/components/SettingsAccounting.vue";
import SettingsMail from "@/components/SettingsMail.vue";
import { useAppStore } from "@/stores/app.store";
import type { AutoBackup } from "@/types";

const { t, locale, setLocale } = useI18n();
const store = useAppStore();
const theme = useTheme();
const themeChoices: ThemeChoice[] = ["system", "light", "dark"];
const enabled = ref(false);
const busy = ref(false);
const exporting = ref(false);

const shop = reactive({ hourly_rate: 0, default_margin_percent: 0 });

// ---- true-size screen: match a bank card
const calibWidth = ref(Math.round(screenPxPerMm() * CARD_WIDTH_MM));
const calibrated = ref(isScreenCalibrated());
function saveCalibration() {
  saveScreenCalibration(calibWidth.value / CARD_WIDTH_MM);
  calibrated.value = true;
}
function resetCalibration() {
  saveScreenCalibration(null);
  calibrated.value = false;
  calibWidth.value = Math.round(screenPxPerMm() * CARD_WIDTH_MM);
}

// ---- invoicing identity and legal mentions
const billing = reactive({
  legal_name: "",
  address_line1: "",
  postal_code: "",
  city: "",
  siren: "",
  siret: "",
  vat_regime: "franchise" as "franchise" | "normal",
  vat_number: "",
  default_vat_rate: 20,
  trade_register: "",
  iban: "",
  bic: "",
  payment_terms_days: 30,
  late_penalty_text: "",
  quote_validity_days: 30,
});
const billingSaved = ref(false);
const billingError = ref("");

async function saveBilling() {
  billingSaved.value = false;
  billingError.value = "";
  const payload: Record<string, unknown> = { ...billing };
  for (const [k, v] of Object.entries(payload)) if (v === "") payload[k] = null;
  try {
    await store.updateShopSettings(payload);
    billingSaved.value = true;
  } catch (err) {
    billingError.value = errorMessage(err, t);
  }
}

// ---- workshop identity, printed in the client plan's title block
const workshop = reactive({ workshop_name: "", workshop_contact: "", workshop_logo: "" });
const workshopSaved = ref(false);
const workshopError = ref("");
const LOGO_MAX_BYTES = 250_000;

function onLogo(ev: Event) {
  workshopError.value = "";
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (!["image/png", "image/jpeg", "image/svg+xml"].includes(file.type)) {
    workshopError.value = t("settings.workshop.logoType");
    return;
  }
  if (file.size > LOGO_MAX_BYTES) {
    workshopError.value = t("settings.workshop.logoSize");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => (workshop.workshop_logo = String(reader.result));
  reader.readAsDataURL(file);
}

async function saveWorkshop() {
  workshopSaved.value = false;
  workshopError.value = "";
  try {
    await store.updateShopSettings({ ...workshop });
    workshopSaved.value = true;
  } catch (err) {
    workshopError.value = errorMessage(err, t);
  }
}
const shopSaved = ref(false);
async function refreshShop() {
  const s = await store.fetchShopSettings();
  shop.hourly_rate = s.hourly_rate;
  shop.default_margin_percent = s.default_margin_percent;
  workshop.workshop_name = s.workshop_name ?? "";
  workshop.workshop_contact = s.workshop_contact ?? "";
  workshop.workshop_logo = s.workshop_logo ?? "";
  for (const key of Object.keys(billing) as (keyof typeof billing)[]) {
    const value = s[key as keyof typeof s];
    (billing as Record<string, unknown>)[key] = value ?? (typeof billing[key] === "number" ? 0 : "");
  }
}
async function saveShop() {
  shopSaved.value = false;
  await store.updateShopSettings(shop);
  shopSaved.value = true;
}

async function refresh() {
  enabled.value = (await store.mockDataStatus()).enabled;
}
onMounted(() => {
  refresh();
  refreshShop();
  loadAutoBackup();
});

// ---- daily automatic backup (desktop build only: the section stays hidden under Docker)
const auto = ref<AutoBackup | null>(null);
const autoForm = reactive({ enabled: true, directory: "", keep_days: 30 });
const autoBusy = ref(false);
const autoMsg = ref("");
const autoError = ref("");
async function loadAutoBackup() {
  try {
    auto.value = await store.fetchAutoBackup();
    Object.assign(autoForm, { enabled: auto.value.enabled, directory: auto.value.directory, keep_days: auto.value.keep_days });
  } catch {
    auto.value = null;
  }
}
async function autoAction(action: () => Promise<AutoBackup>, done: string) {
  autoBusy.value = true;
  autoMsg.value = "";
  autoError.value = "";
  try {
    auto.value = await action();
    if (auto.value.last_error) autoError.value = auto.value.last_error;
    else autoMsg.value = t(done);
  } catch (err) {
    autoError.value = errorMessage(err, t);
  } finally {
    autoBusy.value = false;
  }
}
const saveAuto = () => autoAction(() => store.saveAutoBackup({ ...autoForm, directory: autoForm.directory.trim() }), "autoBackup.saved");
const runAuto = () => autoAction(() => store.runAutoBackup(), "autoBackup.done");
const lastBackupLabel = computed(() => {
  if (!auto.value?.last_at) return t("autoBackup.never");
  const d = new Date(auto.value.last_at);
  return t("autoBackup.last", { when: d.toLocaleString(locale.value === "fr" ? "fr-FR" : "en-GB", { dateStyle: "long", timeStyle: "short" }), file: auto.value.last_file ?? "" });
});

async function seed() {
  busy.value = true;
  try {
    await store.seedMockData();
    await refresh();
  } finally {
    busy.value = false;
  }
}

async function clear() {
  if (!confirm(t("settings.mockData.confirmClear"))) return;
  busy.value = true;
  try {
    await store.clearMockData();
    await refresh();
  } finally {
    busy.value = false;
  }
}

// ---- restorable backup
const backupBusy = ref(false);
const backupMsg = ref("");
const backupError = ref("");

function saveJson(data: unknown, name: string) {
  const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function downloadBackup() {
  backupBusy.value = true;
  backupError.value = "";
  try {
    saveJson(await store.downloadBackup(), `knifeforge-sauvegarde-${new Date().toISOString().slice(0, 10)}.json`);
  } catch (err) {
    backupError.value = errorMessage(err, t);
  } finally {
    backupBusy.value = false;
  }
}


async function exportData() {
  exporting.value = true;
  try {
    const data = await store.exportData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `knifeforge-export-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <div class="page max-w-[1600px]">
    <header class="page-head"><h1 class="page-title">{{ t("settings.title") }}</h1></header>

    <div class="grid gap-6 lg:grid-cols-2 2xl:grid-cols-3 items-start">
      <div class="settings-col">
        <section class="sheet p-5" aria-labelledby="workshop-title">
          <h2 id="workshop-title" class="sheet-title">{{ t("settings.workshop") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.workshop.hint") }}</p>
          <div class="mt-4 grid sm:grid-cols-[1fr_auto] gap-5">
            <div class="space-y-3">
              <label class="block">
                <span class="field-label">{{ t("settings.workshop.name") }}</span>
                <input v-model="workshop.workshop_name" maxlength="120" autocomplete="organization" class="input w-full" />
              </label>
              <label class="block">
                <span class="field-label">{{ t("settings.workshop.contact") }}</span>
                <input v-model="workshop.workshop_contact" maxlength="200" :placeholder="t('settings.workshop.contactExample')" class="input w-full" />
              </label>
            </div>
            <div>
              <span class="field-label">{{ t("settings.workshop.logo") }}</span>
              <div class="w-44 h-20 rounded-lg border border-dashed border-slate-300 bg-slate-50 flex items-center justify-center overflow-hidden">
                <img v-if="workshop.workshop_logo" :src="workshop.workshop_logo" :alt="t('settings.workshop.logoAlt')" class="max-w-full max-h-full object-contain" />
                <span v-else class="text-xs text-slate-500 px-2 text-center">{{ t("settings.workshop.noLogo") }}</span>
              </div>
              <div class="mt-2 flex items-center gap-3">
                <label class="link-action cursor-pointer">
                  {{ workshop.workshop_logo ? t("settings.workshop.replaceLogo") : t("settings.workshop.addLogo") }}
                  <input type="file" accept="image/png,image/jpeg,image/svg+xml" class="sr-only" @change="onLogo" />
                </label>
                <button v-if="workshop.workshop_logo" type="button" class="link-danger" @click="workshop.workshop_logo = ''">{{ t("common.delete") }}</button>
              </div>
            </div>
          </div>
          <div class="mt-4 flex items-center gap-3">
            <button class="btn btn-primary" @click="saveWorkshop">{{ t("common.save") }}</button>
            <span v-if="workshopSaved" class="text-sm text-green-700" role="status">{{ t("settings.shop.saved") }}</span>
            <span v-if="workshopError" class="text-sm text-red-700" role="alert">{{ workshopError }}</span>
          </div>
        </section>
        <div class="sheet p-5">
          <h2 class="sheet-title">{{ t("settings.shop") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.shop.hint") }}</p>
          <div class="mt-3 flex items-end gap-3 flex-wrap">
            <div>
              <label class="field-label" for="settings-f1">{{ t("settings.shop.hourlyRate") }}</label>
              <input id="settings-f1" v-model.number="shop.hourly_rate" type="number" step="any" min="0" class="w-36 input" />
            </div>
            <div>
              <label class="field-label" for="settings-f2">{{ t("settings.shop.defaultMargin") }}</label>
              <input id="settings-f2" v-model.number="shop.default_margin_percent" type="number" step="any" min="0" max="99" class="w-36 input" />
            </div>
            <button class="btn btn-primary" @click="saveShop">{{ t("common.save") }}</button>
            <span v-if="shopSaved" class="text-sm text-green-700">{{ t("settings.shop.saved") }}</span>
          </div>
        </div>
      </div>
      <div class="settings-col">
        <section class="sheet p-5" aria-labelledby="billing-title">
          <h2 id="billing-title" class="sheet-title">{{ t("billing.title") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("billing.hint") }}</p>
          <div class="mt-4 flex gap-2" role="radiogroup" :aria-label="t('billing.regime')">
            <button
              v-for="r in ['franchise', 'normal'] as const"
              :key="r"
              role="radio"
              :aria-checked="billing.vat_regime === r"
              class="btn btn-sm border"
              :class="billing.vat_regime === r ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
              @click="billing.vat_regime = r"
            >
              {{ t(`billing.regimes.${r}`) }}
            </button>
          </div>
          <p class="mt-2 text-xs text-slate-500">{{ t(`billing.regimeHint.${billing.vat_regime}`) }}</p>
          <div class="field-grid mt-4 grid sm:grid-cols-2 gap-3">
            <div class="sm:col-span-2">
              <label class="field-label" for="bi-legal">{{ t("billing.legalName") }}</label>
              <input id="bi-legal" v-model="billing.legal_name" class="input w-full" :placeholder="t('billing.legalNameHint')" />
            </div>
            <div class="sm:col-span-2">
              <label class="field-label" for="bi-addr">{{ t("customers.address") }}</label>
              <input id="bi-addr" v-model="billing.address_line1" class="input w-full" autocomplete="street-address" />
            </div>
            <div>
              <label class="field-label" for="bi-pc">{{ t("customers.postalCode") }}</label>
              <input id="bi-pc" v-model="billing.postal_code" class="input w-full" />
            </div>
            <div>
              <label class="field-label" for="bi-city">{{ t("customers.city") }}</label>
              <input id="bi-city" v-model="billing.city" class="input w-full" />
            </div>
            <div>
              <label class="field-label" for="bi-siren">{{ t("customers.siren") }}</label>
              <input id="bi-siren" v-model="billing.siren" inputmode="numeric" maxlength="9" pattern="\d{9}" class="input w-full" />
            </div>
            <div>
              <label class="field-label" for="bi-siret">{{ t("billing.siret") }}</label>
              <input id="bi-siret" v-model="billing.siret" inputmode="numeric" maxlength="14" pattern="\d{14}" class="input w-full" />
            </div>
            <div :class="billing.vat_regime === 'franchise' ? 'sm:col-span-2' : ''">
              <label class="field-label" for="bi-vat">{{ t("customers.vatNumber") }}</label>
              <input id="bi-vat" v-model="billing.vat_number" class="input w-full" placeholder="FR00123456789" :aria-describedby="billing.vat_regime === 'franchise' ? 'bi-vat-hint' : undefined" />
              <p v-if="billing.vat_regime === 'franchise'" id="bi-vat-hint" class="mt-1 text-xs" :class="billing.vat_number ? 'text-slate-500' : 'text-amber-700'">
                {{ t("billing.franchiseVatHint") }}
              </p>
            </div>
            <template v-if="billing.vat_regime === 'normal'">
              <div>
                <label class="field-label" for="bi-rate">{{ t("billing.defaultRate") }}</label>
                <input id="bi-rate" v-model.number="billing.default_vat_rate" type="number" min="0" max="100" step="0.1" class="input w-full" />
              </div>
            </template>
            <div class="sm:col-span-2">
              <label class="field-label" for="bi-rm">{{ t("billing.tradeRegister") }}</label>
              <input id="bi-rm" v-model="billing.trade_register" class="input w-full" :placeholder="t('billing.tradeRegisterHint')" />
            </div>
            <div>
              <label class="field-label" for="bi-iban">IBAN</label>
              <input id="bi-iban" v-model="billing.iban" class="input w-full" autocomplete="off" />
            </div>
            <div>
              <label class="field-label" for="bi-bic">BIC</label>
              <input id="bi-bic" v-model="billing.bic" class="input w-full" autocomplete="off" />
            </div>
            <div>
              <label class="field-label" for="bi-terms">{{ t("billing.paymentTerms") }}</label>
              <input id="bi-terms" v-model.number="billing.payment_terms_days" type="number" min="0" max="120" class="input w-full" />
            </div>
            <div>
              <label class="field-label" for="bi-quote">{{ t("billing.quoteValidity") }}</label>
              <input id="bi-quote" v-model.number="billing.quote_validity_days" type="number" min="1" max="365" class="input w-full" />
            </div>
            <div class="sm:col-span-2">
              <label class="field-label" for="bi-pen">{{ t("billing.latePenalty") }}</label>
              <input id="bi-pen" v-model="billing.late_penalty_text" class="input w-full" :placeholder="t('billing.latePenaltyHint')" />
            </div>
          </div>
          <div class="mt-4 flex items-center gap-3">
            <button class="btn btn-primary" @click="saveBilling">{{ t("common.save") }}</button>
            <span v-if="billingSaved" class="text-sm text-green-700" role="status">{{ t("settings.shop.saved") }}</span>
            <span v-if="billingError" class="text-sm text-red-700" role="alert">{{ billingError }}</span>
          </div>
          <p class="mt-4 text-xs text-slate-500 max-w-prose">{{ t("documents.einvoicingNote") }}</p>
        </section>
        <SettingsMail />
        <SettingsAccounting />
      </div>
      <div class="settings-col">
        <div class="sheet p-5">
          <h2 class="sheet-title">{{ t("settings.language") }}</h2>
          <div class="mt-3 flex gap-2">
            <button
              class="btn btn-sm border"
              :aria-pressed="locale === 'fr'"
              :class="locale === 'fr' ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
              @click="setLocale('fr' as Locale)"
            >
              Français
            </button>
            <button
              class="btn btn-sm border"
              :aria-pressed="locale === 'en'"
              :class="locale === 'en' ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
              @click="setLocale('en' as Locale)"
            >
              English
            </button>
          </div>
        </div>
        <section class="sheet p-5" aria-labelledby="theme-title">
          <h2 id="theme-title" class="sheet-title">{{ t("theme.title") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("theme.hint") }}</p>
          <div class="mt-3 flex gap-2" role="radiogroup" :aria-labelledby="'theme-title'">
            <button
              v-for="c in themeChoices"
              :key="c"
              role="radio"
              :aria-checked="theme.choice.value === c"
              class="btn btn-sm border"
              :class="theme.choice.value === c ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
              @click="theme.setTheme(c)"
            >
              {{ t(`theme.${c}`) }}
            </button>
          </div>
        </section>
        <section class="sheet p-5" aria-labelledby="calib-title">
          <h2 id="calib-title" class="sheet-title">{{ t("calib.screenTitle") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("calib.screenHint") }}</p>
          <div class="mt-4 overflow-x-auto">
            <div
              class="rounded-[3.5%/5.5%] border-2 border-dashed border-accent-600 bg-accent-50 flex items-center justify-center text-xs text-accent-800"
              :style="{ width: `${calibWidth}px`, height: `${(calibWidth * CARD_HEIGHT_MM) / CARD_WIDTH_MM}px` }"
            >
              {{ t("calib.card") }}
            </div>
          </div>
          <label class="mt-3 flex items-center gap-3 text-sm text-slate-700">
            <span class="shrink-0">{{ t("calib.size") }}</span>
            <input v-model.number="calibWidth" type="range" min="200" max="700" step="1" class="flex-1 max-w-md" :aria-label="t('calib.size')" />
            <input v-model.number="calibWidth" type="number" min="200" max="700" class="input-sm w-20 text-right tabular-nums" :aria-label="t('calib.size')" />
          </label>
          <div class="mt-3 flex items-center gap-3">
            <button class="btn btn-primary" @click="saveCalibration">{{ t("calib.save") }}</button>
            <button v-if="calibrated" class="btn btn-outline" @click="resetCalibration">{{ t("calib.reset") }}</button>
            <span class="text-xs text-slate-500">{{ calibrated ? t("calib.calibrated") : t("calib.notCalibrated") }}</span>
          </div>
        </section>
        <div class="sheet p-5">
          <h2 class="sheet-title">{{ t("settings.backup") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.backup.hint") }}</p>
          <div class="mt-3 flex flex-wrap items-center gap-3">
            <button :disabled="backupBusy" class="btn btn-primary" @click="downloadBackup">{{ t("settings.backup.download") }}</button>
            <button :disabled="exporting" class="link-action" @click="exportData">{{ t("settings.backup.export") }}</button>
          </div>
          <div class="mt-3"><BackupRestore @restored="refreshShop" /></div>
          <p class="sheet-hint mt-2 max-w-prose">{{ t("settings.restore.hint") }}</p>
          <p v-if="backupMsg" class="mt-2 text-sm text-green-700" role="status">{{ backupMsg }}</p>
          <p v-if="backupError" class="mt-2 text-sm text-red-700" role="alert">{{ backupError }}</p>
        </div>
        <section v-if="auto" class="sheet p-5" aria-labelledby="auto-backup-title">
          <h2 id="auto-backup-title" class="sheet-title">{{ t("autoBackup.title") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("autoBackup.hint") }}</p>
          <label class="mt-3 flex items-center gap-2 text-sm text-slate-700">
            <input v-model="autoForm.enabled" type="checkbox" /> {{ t("autoBackup.enabled") }}
          </label>
          <label class="block mt-3">
            <span class="field-label">{{ t("autoBackup.directory") }}</span>
            <input v-model="autoForm.directory" type="text" spellcheck="false" class="input w-full font-mono text-xs" />
          </label>
          <label class="block mt-3">
            <span class="field-label">{{ t("autoBackup.keepDays") }}</span>
            <input v-model.number="autoForm.keep_days" type="number" min="1" max="3650" class="input w-28" />
          </label>
          <div class="mt-4 flex flex-wrap items-center gap-3">
            <button :disabled="autoBusy" class="btn btn-primary" @click="saveAuto">{{ t("common.save") }}</button>
            <button :disabled="autoBusy" class="btn btn-outline" @click="runAuto">{{ t("autoBackup.runNow") }}</button>
          </div>
          <p class="mt-3 text-xs text-slate-500">{{ lastBackupLabel }}</p>
          <p v-if="autoMsg" class="mt-2 text-sm text-green-700" role="status">{{ autoMsg }}</p>
          <p v-if="autoError" class="mt-2 text-sm text-red-700" role="alert">{{ autoError }}</p>
        </section>
        <div class="sheet p-5">
          <h2 class="sheet-title">{{ t("settings.mockData") }}</h2>
          <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.mockData.hint") }}</p>
          <p class="mt-3 text-sm">
            {{ t("settings.mockData.status") }}{{ t("common.colon") }}
            <span :class="enabled ? 'text-green-700' : 'text-slate-500'">{{ enabled ? t("settings.mockData.enabled") : t("settings.mockData.disabled") }}</span>
          </p>
          <div class="mt-3 flex gap-3">
            <button :disabled="busy" class="btn btn-outline" @click="seed">{{ t("settings.mockData.seed") }}</button>
            <button :disabled="busy" class="btn btn-outline text-red-700 hover:text-red-800 hover:border-red-300" @click="clear">{{ t("settings.mockData.clear") }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
