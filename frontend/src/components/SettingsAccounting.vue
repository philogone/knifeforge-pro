<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

/** Accounts of the sales journal, and the workshop's own wording for e-mails and reminders. */
const { t } = useI18n();
const store = useAppStore();

const accountKeys = ["account_customers", "account_sales_goods", "account_sales_services", "account_vat", "account_deposits", "account_bank"] as const;
const accounts = reactive<Record<string, string>>({});
const templates = reactive({ send: "", r1: "", r2: "", r3: "" });
const tab = ref<"send" | "r1" | "r2" | "r3">("send");
const msg = ref("");
const error = ref("");

onMounted(async () => {
  const s = await store.fetchShopSettings();
  for (const k of accountKeys) accounts[k] = s[k];
  templates.send = s.email_send_template ?? "";
  templates.r1 = s.reminder_templates?.["1"] ?? "";
  templates.r2 = s.reminder_templates?.["2"] ?? "";
  templates.r3 = s.reminder_templates?.["3"] ?? "";
});

async function save() {
  msg.value = "";
  error.value = "";
  try {
    await store.updateShopSettings({
      ...accounts,
      email_send_template: templates.send.trim(),
      reminder_templates: { "1": templates.r1, "2": templates.r2, "3": templates.r3 },
    });
    msg.value = t("settings.shop.saved");
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}
const placeholders = ["client", "type", "numero", "date", "montant", "reste", "echeance", "jours_retard", "atelier", "iban"];
</script>

<template>
  <section class="sheet p-5" aria-labelledby="acc-settings-title">
    <h2 id="acc-settings-title" class="sheet-title">{{ t("accSettings.title") }}</h2>
    <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("accSettings.hint") }}</p>
    <form class="mt-3" @submit.prevent="save">
      <div class="grid gap-3 grid-cols-2">
        <label v-for="k in accountKeys" :key="k" class="block">
          <span class="field-label">{{ t(`accSettings.${k}`) }}</span>
          <input v-model="accounts[k]" required pattern="[0-9A-Za-z]{1,20}" class="input w-full tabular-nums" />
        </label>
      </div>

      <h3 class="mt-5 text-sm font-semibold text-slate-800">{{ t("accSettings.messages") }}</h3>
      <p class="text-xs text-slate-500 mt-1 max-w-prose">{{ t("accSettings.messagesHint") }}</p>
      <div class="mt-2 flex flex-wrap gap-1" role="tablist">
        <button
          v-for="k in (['send', 'r1', 'r2', 'r3'] as const)"
          :key="k"
          type="button"
          role="tab"
          :aria-selected="tab === k"
          class="px-2.5 py-1 rounded-md text-xs border"
          :class="tab === k ? 'bg-slate-800 text-paper border-slate-800' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="tab = k"
        >
          {{ t(`accSettings.tabs.${k}`) }}
        </button>
      </div>
      <textarea v-model="templates[tab]" rows="8" maxlength="4000" class="input w-full mt-2 text-sm" :placeholder="t('accSettings.builtIn')"
                :aria-label="t(`accSettings.tabs.${tab}`)"></textarea>
      <p class="text-xs text-slate-500">{{ t("accSettings.fields") }} <code v-for="p in placeholders" :key="p" class="mr-1">{{ "{" + p + "}" }}</code></p>
      <div class="mt-3 flex items-center gap-3">
        <button type="submit" class="btn btn-primary">{{ t("common.save") }}</button>
        <span v-if="msg" class="text-sm text-emerald-700" role="status">{{ msg }}</span>
      </div>
      <p v-if="error" class="mt-2 text-sm text-red-700" role="alert">{{ error }}</p>
    </form>
  </section>
</template>
