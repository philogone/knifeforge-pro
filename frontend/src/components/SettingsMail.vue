<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { MailSettings } from "@/types";

/** The workshop's outgoing mail account: editable in the desktop build, read from the
 * server's environment under Docker. The password is never sent back. */
const { t } = useI18n();
const store = useAppStore();

const state = ref<MailSettings | null>(null);
const form = reactive({ host: "", port: 587, security: "starttls" as MailSettings["security"], user: "", password: "", from_address: "", from_name: "" });
const testTo = ref("");
const busy = ref(false);
const msg = ref("");
const error = ref("");

function fill(s: MailSettings) {
  state.value = s;
  Object.assign(form, { host: s.host, port: s.port, security: s.security, user: s.user, password: "", from_address: s.from_address, from_name: s.from_name });
}

onMounted(async () => {
  try {
    fill(await store.fetchMailSettings());
  } catch (err) {
    error.value = errorMessage(err, t);
  }
});

// common providers: port and security filled in, the user keeps control
const presets: Record<string, [string, number, MailSettings["security"]]> = {
  gmail: ["smtp.gmail.com", 587, "starttls"],
  outlook: ["smtp-mail.outlook.com", 587, "starttls"],
  orange: ["smtp.orange.fr", 465, "ssl"],
  free: ["smtp.free.fr", 465, "ssl"],
  ovh: ["ssl0.ovh.net", 465, "ssl"],
};
function preset(ev: Event) {
  const p = presets[(ev.target as HTMLSelectElement).value];
  if (p) [form.host, form.port, form.security] = p;
}

async function act(action: () => Promise<MailSettings>, done: string) {
  busy.value = true;
  msg.value = "";
  error.value = "";
  try {
    fill(await action());
    msg.value = t(done);
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}
const save = () =>
  act(() => store.saveMailSettings({ ...form, password: form.password === "" ? null : form.password }), "mailSettings.saved");
const test = () => act(() => store.testMail(testTo.value.trim()), "mailSettings.testSent");
</script>

<template>
  <section class="sheet p-5" aria-labelledby="mail-settings-title">
    <h2 id="mail-settings-title" class="sheet-title">{{ t("mailSettings.title") }}</h2>
    <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("mailSettings.hint") }}</p>
    <template v-if="state">
      <p class="mt-2 text-sm" :class="state.configured ? 'text-emerald-700' : 'text-amber-700'">
        {{ state.configured ? t("mailSettings.ready", { host: state.host }) : t("mailSettings.notReady") }}
      </p>

      <form v-if="state.editable" class="mt-3 grid gap-3 sm:grid-cols-2" @submit.prevent="save">
        <label class="block sm:col-span-2">
          <span class="field-label">{{ t("mailSettings.provider") }}</span>
          <select class="input w-full" @change="preset">
            <option value="">{{ t("mailSettings.providerOther") }}</option>
            <option value="gmail">Gmail</option>
            <option value="outlook">Outlook / Hotmail</option>
            <option value="orange">Orange</option>
            <option value="free">Free</option>
            <option value="ovh">OVH</option>
          </select>
        </label>
        <label class="block">
          <span class="field-label">{{ t("mailSettings.host") }}</span>
          <input v-model="form.host" required class="input w-full" spellcheck="false" />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="block">
            <span class="field-label">{{ t("mailSettings.port") }}</span>
            <input v-model.number="form.port" type="number" min="1" max="65535" class="input w-full" />
          </label>
          <label class="block">
            <span class="field-label">{{ t("mailSettings.security") }}</span>
            <select v-model="form.security" class="input w-full">
              <option value="starttls">STARTTLS</option>
              <option value="ssl">SSL/TLS</option>
              <option value="none">{{ t("mailSettings.none") }}</option>
            </select>
          </label>
        </div>
        <label class="block">
          <span class="field-label">{{ t("mailSettings.user") }}</span>
          <input v-model="form.user" autocomplete="off" class="input w-full" spellcheck="false" />
        </label>
        <label class="block">
          <span class="field-label">{{ t("mailSettings.password") }}</span>
          <input v-model="form.password" type="password" autocomplete="new-password" class="input w-full"
                 :placeholder="state.password_set ? t('mailSettings.passwordKept') : ''" />
        </label>
        <label class="block">
          <span class="field-label">{{ t("mailSettings.from") }}</span>
          <input v-model="form.from_address" type="email" class="input w-full" :placeholder="t('mailSettings.fromHint')" />
        </label>
        <label class="block">
          <span class="field-label">{{ t("mailSettings.fromName") }}</span>
          <input v-model="form.from_name" maxlength="120" class="input w-full" />
        </label>
        <p class="sm:col-span-2 text-xs text-slate-500">{{ t("mailSettings.appPassword") }}</p>
        <div class="sm:col-span-2">
          <button type="submit" class="btn btn-primary" :disabled="busy">{{ t("common.save") }}</button>
        </div>
      </form>
      <p v-else class="mt-2 text-sm text-slate-600">{{ t("mailSettings.docker") }}</p>

      <form v-if="state.configured" class="mt-4 flex flex-wrap items-end gap-2" @submit.prevent="test">
        <label class="block">
          <span class="field-label">{{ t("mailSettings.testTo") }}</span>
          <input v-model="testTo" type="email" required class="input" />
        </label>
        <button type="submit" class="btn btn-outline" :disabled="busy">{{ t("mailSettings.test") }}</button>
      </form>
    </template>
    <p v-if="msg" class="mt-2 text-sm text-emerald-700" role="status">{{ msg }}</p>
    <p v-if="error" class="mt-2 text-sm text-red-700" role="alert">{{ error }}</p>
  </section>
</template>
