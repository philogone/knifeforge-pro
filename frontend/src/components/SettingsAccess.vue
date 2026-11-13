<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

/** The workshop's access: changed here in the desktop build, in .env under Docker. */
const { t } = useI18n();
const store = useAppStore();

const editable = ref<boolean | null>(null);
const form = reactive({ current: "", next: "", confirm: "", email: "" });
const busy = ref(false);
const msg = ref("");
const error = ref("");

onMounted(async () => {
  try {
    editable.value = (await store.fetchMailSettings()).editable;
  } catch {
    editable.value = false;
  }
});

async function save() {
  msg.value = "";
  error.value = "";
  if (form.next !== form.confirm) {
    error.value = t("setup.mismatch");
    return;
  }
  busy.value = true;
  try {
    await store.changePassword(form.current, form.next, form.email.trim() || undefined);
    Object.assign(form, { current: "", next: "", confirm: "", email: "" });
    msg.value = t("access.changed");
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="sheet p-5" aria-labelledby="access-title">
    <h2 id="access-title" class="sheet-title">{{ t("access.title") }}</h2>
    <form v-if="editable" class="mt-3 grid gap-3" @submit.prevent="save">
      <label class="block">
        <span class="field-label">{{ t("access.current") }}</span>
        <input v-model="form.current" type="password" required autocomplete="current-password" class="input w-full" />
      </label>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="field-label">{{ t("access.new") }}</span>
          <input v-model="form.next" type="password" required minlength="10" maxlength="72" autocomplete="new-password" class="input w-full" />
        </label>
        <label class="block">
          <span class="field-label">{{ t("setup.confirm") }}</span>
          <input v-model="form.confirm" type="password" required minlength="10" maxlength="72" autocomplete="new-password" class="input w-full" />
        </label>
      </div>
      <label class="block">
        <span class="field-label">{{ t("access.email") }}</span>
        <input v-model="form.email" type="email" autocomplete="username" class="input w-full" :placeholder="t('access.emailKept')" />
      </label>
      <p class="text-xs text-slate-500">{{ t("setup.passwordHint") }}</p>
      <div>
        <button type="submit" class="btn btn-primary" :disabled="busy">{{ t("access.save") }}</button>
      </div>
    </form>
    <p v-else-if="editable === false" class="mt-2 text-sm text-slate-600 max-w-prose">{{ t("access.docker") }}</p>
    <p v-if="msg" class="mt-2 text-sm text-emerald-700" role="status">{{ msg }}</p>
    <p v-if="error" class="mt-2 text-sm text-red-700" role="alert">{{ error }}</p>
  </section>
</template>
