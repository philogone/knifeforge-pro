<script setup lang="ts">
import { useI18n } from "@/i18n";
import type { DocumentEvent } from "@/types";

defineProps<{ events: DocumentEvent[] }>();
const { t, locale } = useI18n();
const fmt = (iso: string) =>
  new Date(iso).toLocaleString(locale.value === "fr" ? "fr-FR" : "en-GB", { dateStyle: "short", timeStyle: "short" });
</script>

<template>
  <section class="sheet p-5" aria-labelledby="history-title">
    <h2 id="history-title" class="sheet-title mb-3">{{ t("history.title") }}</h2>
    <ol v-if="events.length" class="space-y-2 text-sm">
      <li v-for="e in [...events].reverse()" :key="e.id" class="flex flex-wrap gap-x-3 border-t border-slate-100 pt-2 first:border-0 first:pt-0">
        <span class="tabular-nums text-slate-500 w-32 shrink-0">{{ fmt(e.at) }}</span>
        <span class="font-medium">
          {{ e.kind === "sent" ? t("history.sent") : t("history.reminder", { level: e.level ?? 1 }) }}
          <span class="font-normal text-slate-600">· {{ t(`mail.channels.${e.channel}`) }}</span>
        </span>
        <span v-if="e.recipient" class="text-slate-600">{{ e.recipient }}</span>
        <span v-if="e.note" class="basis-full text-slate-600 sm:pl-[8.75rem]">{{ e.note }}</span>
      </li>
    </ol>
    <p v-else class="text-sm text-slate-500">{{ t("history.none") }}</p>
  </section>
</template>
