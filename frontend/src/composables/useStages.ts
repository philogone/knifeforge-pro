import { ref } from "vue";

import { apiFetch } from "@/composables/useApi";
import { useI18n } from "@/i18n";

export interface Stage {
  key: string;
  label: string | null;
  used: number;
}

// the workshop's stages, shared by every page (loaded once, refreshed after a change)
const stages = ref<Stage[]>([]);
let loading: Promise<void> | null = null;

export function loadStages(force = false): Promise<void> {
  if (!loading || force) {
    loading = apiFetch<Stage[]>("/admin/settings/stages").then((s) => {
      stages.value = s;
    });
  }
  return loading;
}

export function setStages(s: Stage[]): void {
  stages.value = s;
}

export function useStages() {
  const { t } = useI18n();
  /** a built-in stage is translated; the workshop's own carries its label */
  const stageLabel = (key: string) => {
    const s = stages.value.find((x) => x.key === key);
    if (s?.label) return s.label;
    const k = `orders.stage.${key}`;
    const text = t(k);
    return text === k ? key : text;
  };
  return { stages, stageLabel, loadStages };
}
