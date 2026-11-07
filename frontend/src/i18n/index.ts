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
  /** fixed-precision number in the reader's convention ("182,0" in French) */
  const num = (n: number, digits = 1): string => formatFixed(n, locale.value, digits);
  /** an amount in euros, always two decimals ("180,00 €") */
  const money = (n: number): string => formatMoney(n, locale.value);
  return { t, locale: computed(() => locale.value), setLocale, num, money };
}

function tag(loc: Locale): string {
  return loc === "fr" ? "fr-FR" : "en-US";
}

/** Fixed decimals, locale-aware: replaces `toFixed`, whose dot a French reader misreads. */
export function formatFixed(n: number, loc: Locale, digits = 1): string {
  return n.toLocaleString(tag(loc), { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** The workshop prices everything in euros. */
export function formatMoney(n: number, loc: Locale): string {
  return n.toLocaleString(tag(loc), { style: "currency", currency: "EUR" });
}

/** Locale-aware decimal ("1,94" in French, "1.94" in English) — never a bare "1.939" a French reader takes for 1939. */
export function formatDecimal(n: number, loc: Locale, maxDigits = 2): string {
  return n.toLocaleString(loc === "fr" ? "fr-FR" : "en-US", { maximumFractionDigits: maxDigits });
}
