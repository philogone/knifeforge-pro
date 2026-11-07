import { computed, ref, type Ref } from "vue";

/** lower case, accents stripped: "Acier trempé" matches "acier trempe" */
export function normalize(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** every word of the query appears somewhere in the haystack fields */
export function matches(fields: (string | null | undefined)[], query: string): boolean {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = normalize(fields.filter(Boolean).join(" "));
  return words.every((w) => hay.includes(w));
}

export interface SortOption<T> {
  key: string;
  label: string;
  compare: (a: T, b: T) => number;
}

/**
 * Search + sort state for a list page. The list itself stays the source of truth;
 * `visible` is what the page renders.
 */
export function useListSearch<T>(items: Ref<T[]> | (() => T[]), fields: (item: T) => (string | null | undefined)[], sorts: SortOption<T>[]) {
  const query = ref("");
  const sortKey = ref(sorts[0]?.key ?? "");
  const source = typeof items === "function" ? computed(items) : items;
  const visible = computed(() => {
    const sort = sorts.find((s) => s.key === sortKey.value);
    const found = source.value.filter((item) => matches(fields(item), query.value));
    return sort ? [...found].sort(sort.compare) : found;
  });
  return { query, sortKey, visible, total: computed(() => source.value.length) };
}

/** French-aware alphabetical order ("Écorce" sorts with the E) */
export const byText = (a: string, b: string) => a.localeCompare(b, "fr", { sensitivity: "base", numeric: true });
