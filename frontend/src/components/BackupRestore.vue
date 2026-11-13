<script setup lang="ts">
import { ref } from "vue";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { BackupInfo } from "@/types";

/** Pick a backup file, see what it holds, then replace everything with it (Settings, first run). */
defineProps<{ label?: string }>();
const emit = defineEmits<{ (e: "restored", total: number): void }>();

const { t, locale } = useI18n();
const store = useAppStore();

const data = ref<unknown>(null);
const fileName = ref("");
const info = ref<BackupInfo | null>(null);
const busy = ref(false);
const error = ref("");
const done = ref("");

async function onFile(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  error.value = "";
  done.value = "";
  info.value = null;
  try {
    data.value = JSON.parse(await file.text());
  } catch {
    error.value = t("settings.restore.notJson");
    return;
  }
  fileName.value = file.name;
  try {
    info.value = await store.inspectBackup(data.value);
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

async function restore() {
  if (!info.value || !confirm(t("settings.restore.confirm", { name: fileName.value }))) return;
  busy.value = true;
  error.value = "";
  try {
    const res = await store.restoreBackup(data.value);
    const total = Object.values(res.restored).reduce((a, b) => a + b, 0);
    done.value = t("settings.restore.done", { n: total });
    info.value = null;
    emit("restored", total);
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString(locale.value === "fr" ? "fr-FR" : "en-GB", { dateStyle: "long", timeStyle: "short" }) : "—";
</script>

<template>
  <div>
    <label class="btn btn-outline cursor-pointer">
      {{ label ?? t("settings.restore.button") }}
      <input type="file" accept="application/json,.json" class="sr-only" :disabled="busy" @change="onFile" />
    </label>

    <div v-if="info" class="mt-3 rounded-lg border border-slate-200 p-3 text-sm" role="region" :aria-label="t('restore.previewTitle')">
      <p class="font-medium">{{ t("restore.previewTitle") }} · {{ fileName }}</p>
      <dl class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
        <dt class="text-slate-500">{{ t("restore.made") }}</dt><dd>{{ when(info.created_at) }}</dd>
        <dt v-if="info.workshop" class="text-slate-500">{{ t("restore.workshop") }}</dt><dd v-if="info.workshop">{{ info.workshop }}</dd>
        <template v-for="(n, key) in info.counts" :key="key">
          <dt class="text-slate-500">{{ t(`restore.counts.${key}`) }}</dt><dd class="tabular-nums">{{ n }}</dd>
        </template>
      </dl>
      <p class="mt-2" :class="info.compatibility === 'newer' || info.compatibility === 'unknown' ? 'text-red-700' : 'text-slate-600'">
        {{ t(`restore.compat.${info.compatibility}`) }}
      </p>
      <div class="mt-3 flex flex-wrap gap-2">
        <button
          class="btn btn-primary"
          :disabled="busy || info.compatibility === 'newer' || info.compatibility === 'unknown'"
          @click="restore"
        >
          {{ t("restore.replace") }}
        </button>
        <button class="btn btn-outline" :disabled="busy" @click="info = null">{{ t("common.cancel") }}</button>
      </div>
    </div>
    <p v-if="done" class="mt-2 text-sm text-emerald-700" role="status">{{ done }}</p>
    <p v-if="error" class="mt-2 text-sm text-red-700" role="alert">{{ error }}</p>
  </div>
</template>
