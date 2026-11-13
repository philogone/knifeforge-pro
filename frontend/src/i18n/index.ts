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

// trade profile: a blacksmith's workshop reads its own words where the knifemaker's differ
export type Trade = "knifemaker" | "blacksmith";
const TRADE_KEY = "knifeforge_trade";
function savedTrade(): Trade {
  try {
    return localStorage.getItem(TRADE_KEY) === "blacksmith" ? "blacksmith" : "knifemaker";
  } catch {
    return "knifemaker";
  }
}
const trade = ref<Trade>(savedTrade());
export function setTrade(next: Trade): void {
  trade.value = next;
  try {
    localStorage.setItem(TRADE_KEY, next);
  } catch {
    // private window: the trade still applies for this session
  }
}
export function currentTrade() {
  return computed(() => trade.value);
}

export function setLocale(next: Locale): void {
  locale.value = next;
  localStorage.setItem(STORAGE_KEY, next);
}

export function useI18n() {
  const t = (key: string, vars?: Record<string, string | number>): string => {
    // counted messages: "{n} pièce" / "{n} pièces" (French treats 0 and 1 as singular)
    const count = typeof vars?.n === "number" ? vars.n : typeof vars?.parts === "number" ? vars.parts : null;
    if (count !== null) {
      const one = locale.value === "fr" ? Math.abs(count) < 2 : Math.abs(count) === 1;
      const form = `${key}.${one ? "one" : "many"}`;
      if (dictionaries[locale.value][form] ?? dictionaries.en[form]) key = form;
    }
    const overlay = trade.value === "blacksmith" ? `@blacksmith:${key}` : null;
    let text =
      (overlay && (dictionaries[locale.value][overlay] ?? dictionaries.en[overlay])) ?? dictionaries[locale.value][key] ?? dictionaries.en[key] ?? key;
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
  /** a stock quantity with its unit, as the API sends it ("unit", "mm", "mm^2") */
  const qty = (n: number, unit: string): string =>
    `${formatDecimal(n, locale.value, 3)} ${unit === "unit" ? t(n > 1 ? "common.unitMany" : "common.unitOne") : unit.replace("^2", "²")}`;
  return { t, locale: computed(() => locale.value), setLocale, num, money, qty };
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
