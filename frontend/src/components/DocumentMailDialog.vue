<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { MailPurpose, SalesDocument } from "@/types";

/** Send the document, or a payment reminder (by e-mail, or noted as a letter / phone call). */
const props = defineProps<{ doc: SalesDocument; purpose: MailPurpose }>();
const emit = defineEmits<{ (e: "done", doc: SalesDocument): void; (e: "close"): void }>();

const { t } = useI18n();
const store = useAppStore();

const reminder = computed(() => props.purpose !== "send");
const form = reactive({ channel: "email" as "email" | "letter" | "phone", to: "", cc: "", subject: "", body: "", note: "" });
const attachment = ref("");
const configured = ref(true);
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const level = ref(Number(props.purpose) || 1);

const split = (v: string) => v.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);

async function load(purpose: MailPurpose) {
  loading.value = true;
  error.value = "";
  try {
    const draft = await store.mailDraft(props.doc.id, purpose);
    form.to = draft.to.join(", ");
    form.subject = draft.subject;
    form.body = draft.body;
    attachment.value = draft.attachment;
    configured.value = draft.configured;
    if (!draft.configured && reminder.value) form.channel = "letter";
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    loading.value = false;
  }
}
onMounted(() => load(props.purpose));

async function changeLevel() {
  await load(String(level.value) as MailPurpose);
}

async function submit() {
  busy.value = true;
  error.value = "";
  try {
    let doc: SalesDocument;
    if (!reminder.value) {
      doc = await store.sendDocument(props.doc.id, { to: split(form.to), cc: split(form.cc), subject: form.subject, body: form.body });
    } else if (form.channel === "email") {
      doc = await store.remind(props.doc.id, { level: level.value, channel: "email", to: split(form.to), subject: form.subject, body: form.body, note: form.note || undefined });
    } else {
      doc = await store.remind(props.doc.id, { level: level.value, channel: form.channel, note: form.note || undefined });
    }
    emit("done", doc);
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

function copyText() {
  navigator.clipboard?.writeText(form.body).catch(() => {});
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" role="dialog" aria-modal="true" aria-labelledby="mail-title" @keydown.esc="emit('close')">
    <div class="sheet w-full max-w-2xl max-h-[90vh] overflow-y-auto p-5">
      <h2 id="mail-title" class="sheet-title mb-1">{{ reminder ? t("mail.reminderTitle", { number: doc.number ?? "" }) : t("mail.sendTitle", { number: doc.number ?? "" }) }}</h2>
      <p class="text-sm text-slate-600 mb-4">{{ reminder ? t("mail.reminderLead") : t("mail.sendLead") }}</p>

      <div v-if="reminder" class="grid gap-3 sm:grid-cols-2 mb-3">
        <label class="block">
          <span class="field-label">{{ t("mail.level") }}</span>
          <select v-model.number="level" class="input w-full" @change="changeLevel">
            <option :value="1">{{ t("mail.levels.1") }}</option>
            <option :value="2">{{ t("mail.levels.2") }}</option>
            <option :value="3">{{ t("mail.levels.3") }}</option>
          </select>
        </label>
        <label class="block">
          <span class="field-label">{{ t("mail.channel") }}</span>
          <select v-model="form.channel" class="input w-full">
            <option value="email" :disabled="!configured">{{ t("mail.channels.email") }}</option>
            <option value="letter">{{ t("mail.channels.letter") }}</option>
            <option value="phone">{{ t("mail.channels.phone") }}</option>
          </select>
        </label>
      </div>

      <p v-if="!configured && (!reminder || form.channel === 'email')" class="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        {{ t("mail.notConfigured") }} <router-link to="/settings" class="underline underline-offset-2">{{ t("mail.goSettings") }}</router-link>
      </p>
      <p v-if="reminder && level === 3" class="mb-3 text-sm text-slate-600">{{ t("mail.formalNotice") }}</p>

      <p v-if="loading" class="text-sm text-slate-500">{{ t("common.loading") }}</p>
      <form v-else class="space-y-3" @submit.prevent="submit">
        <template v-if="!reminder || form.channel === 'email'">
          <label class="block">
            <span class="field-label">{{ t("mail.to") }}</span>
            <input v-model="form.to" required class="input w-full" :placeholder="t('mail.toHint')" />
          </label>
          <label v-if="!reminder" class="block">
            <span class="field-label">{{ t("mail.cc") }}</span>
            <input v-model="form.cc" class="input w-full" />
          </label>
          <label class="block">
            <span class="field-label">{{ t("mail.subject") }}</span>
            <input v-model="form.subject" required maxlength="255" class="input w-full" />
          </label>
          <label class="block">
            <span class="field-label">{{ t("mail.body") }}</span>
            <textarea v-model="form.body" required rows="10" class="input w-full font-[inherit]"></textarea>
          </label>
          <p class="text-xs text-slate-500">{{ t("mail.attachment", { name: attachment }) }}</p>
        </template>
        <template v-else>
          <label class="block">
            <span class="field-label">{{ t("mail.letterText") }}</span>
            <textarea v-model="form.body" rows="8" class="input w-full" readonly></textarea>
          </label>
          <button type="button" class="link-action text-sm" @click="copyText">{{ t("mail.copy") }}</button>
          <label class="block">
            <span class="field-label">{{ t("mail.note") }}</span>
            <input v-model="form.note" maxlength="2000" class="input w-full" :placeholder="form.channel === 'phone' ? t('mail.notePhone') : t('mail.noteLetter')" />
          </label>
        </template>
        <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
        <div class="flex flex-wrap gap-2 pt-1">
          <button type="submit" class="btn btn-primary" :disabled="busy || ((!reminder || form.channel === 'email') && !configured)">
            {{ !reminder ? t("mail.send") : form.channel === "email" ? t("mail.sendReminder") : t("mail.recordReminder") }}
          </button>
          <button type="button" class="btn btn-outline" @click="emit('close')">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>
  </div>
</template>
