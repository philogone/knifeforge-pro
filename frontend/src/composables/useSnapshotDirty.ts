import { computed, ref, type ComputedRef } from "vue";

/**
 * "Has this reactive form changed since it was last loaded/saved?" by comparing against a snapshot.
 * Unlike a `watch` that sets a flag, it can't be re-triggered by the very assignments that load the
 * form (watchers run after the current tick), and editing a field back to its saved value is clean again.
 */
export function useSnapshotDirty(source: () => unknown): { dirty: ComputedRef<boolean>; markClean: () => void } {
  const saved = ref<string | null>(null);
  const dirty = computed(() => saved.value !== null && JSON.stringify(source()) !== saved.value);
  const markClean = () => {
    saved.value = JSON.stringify(source());
  };
  return { dirty, markClean };
}
