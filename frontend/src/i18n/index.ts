import { computed, ref } from "vue";

import { en } from "@/i18n/en";
import { fr } from "@/i18n/fr";

export type Locale = "fr" | "en";

const STORAGE_KEY = "knifeforge_locale";
const dictionaries: Record<Locale, Record<string, string>> = { fr, en };

function detectDefault(): Locale {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "fr" || saved === "en") return saved;
  return navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

const locale = ref<Locale>(detectDefault());

export function setLocale(next: Locale): void {
  locale.value = next;
  localStorage.setItem(STORAGE_KEY, next);
}

export function useI18n() {
  const t = (key: string, vars?: Record<string, string | number>): string => {
    let text = dictionaries[locale.value][key] ?? dictionaries.en[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        text = text.replace(`{${k}}`, String(v));
      }
    }
    return text;
  };
  return { t, locale: computed(() => locale.value), setLocale };
}
