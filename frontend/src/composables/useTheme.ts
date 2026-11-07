import { computed, ref } from "vue";

export type ThemeChoice = "system" | "light" | "dark";

const STORAGE_KEY = "knifeforge_theme";
const media = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function readChoice(): ThemeChoice {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
  } catch {
    // storage blocked: follow the system
  }
  return "system";
}

const choice = ref<ThemeChoice>(readChoice());
const systemDark = ref(media?.matches ?? false);
media?.addEventListener("change", (e) => (systemDark.value = e.matches));

const isDark = computed(() => (choice.value === "system" ? systemDark.value : choice.value === "dark"));

/** listeners that must repaint something not driven by CSS (the editor's canvases) */
const listeners = new Set<() => void>();

function apply() {
  document.documentElement.classList.toggle("dark", isDark.value);
  for (const fn of listeners) fn();
}

/** call once at start-up, before mounting, so the first paint is already in the right theme */
export function initTheme(): void {
  apply();
  media?.addEventListener("change", apply);
}

export function useTheme() {
  function setTheme(next: ThemeChoice) {
    choice.value = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // not persisted, still applied
    }
    apply();
  }
  /** nav button: flips between light and dark, leaving "system" for Settings */
  function toggle() {
    setTheme(isDark.value ? "light" : "dark");
  }
  function onChange(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }
  return { choice: computed(() => choice.value), isDark, setTheme, toggle, onChange };
}
