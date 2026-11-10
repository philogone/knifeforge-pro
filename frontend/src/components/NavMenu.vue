<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { useI18n } from "@/i18n";

export interface NavItem {
  to: string;
  key: string;
  desc: string;
}

const props = defineProps<{ label: string; items: NavItem[] }>();

const { t } = useI18n();
const route = useRoute();
const open = ref(false);
const root = ref<HTMLElement | null>(null);
const id = `navmenu-${Math.random().toString(36).slice(2, 8)}`;

/** a detail page (/orders/3, /designs/1) keeps its section lit */
function isActive(to: string): boolean {
  if (to === "/") return route.path === "/";
  return route.path === to || route.path.startsWith(`${to}/`);
}
const groupActive = computed(() => props.items.some((i) => isActive(i.to)));

// mouse users get the menu on hover (one gesture to any page); a short grace period lets the
// pointer cross the gap between the button and the panel
let closeTimer: number | undefined;
let openedByHover = false;
function hoverOpen(e: PointerEvent) {
  if (e.pointerType !== "mouse") return;
  window.clearTimeout(closeTimer);
  if (!open.value) openedByHover = true;
  open.value = true;
}
function hoverClose(e: PointerEvent) {
  if (e.pointerType !== "mouse") return;
  closeTimer = window.setTimeout(() => (open.value = false), 150);
}

// the click that follows a hover must not close the menu the hover just opened
function onClick() {
  if (openedByHover) {
    openedByHover = false;
    open.value = true;
  } else {
    open.value = !open.value;
  }
}

function onDocPointer(e: PointerEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false;
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape" && open.value) {
    open.value = false;
    root.value?.querySelector<HTMLButtonElement>("button")?.focus();
  }
}
watch(open, (o) => {
  if (!o) openedByHover = false;
  if (o) {
    document.addEventListener("pointerdown", onDocPointer);
    document.addEventListener("keydown", onKey);
  } else {
    document.removeEventListener("pointerdown", onDocPointer);
    document.removeEventListener("keydown", onKey);
  }
});
watch(() => route.fullPath, () => (open.value = false));
onBeforeUnmount(() => {
  window.clearTimeout(closeTimer);
  document.removeEventListener("pointerdown", onDocPointer);
  document.removeEventListener("keydown", onKey);
});
</script>

<template>
  <div ref="root" class="relative h-full" @pointerenter="hoverOpen" @pointerleave="hoverClose">
    <button
      type="button"
      class="relative h-full px-3 flex items-center gap-1.5 text-sm whitespace-nowrap transition-colors"
      :class="groupActive ? 'text-slate-900 font-medium nav-active' : 'text-slate-600 hover:text-slate-900'"
      :aria-expanded="open"
      :aria-controls="id"
      @click="onClick"
    >
      {{ label }}
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="transition-transform" :class="open ? 'rotate-180' : ''">
        <path d="M2 3.5l3 3 3-3" />
      </svg>
    </button>
    <div
      v-show="open"
      :id="id"
      class="absolute left-0 top-full z-50 mt-px w-72 rounded-b-lg border border-t-0 border-slate-200 bg-paper p-1.5 shadow-lg"
    >
      <router-link
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="block rounded-md px-3 py-2 transition-colors"
        :class="isActive(item.to) ? 'bg-accent-50 text-accent-800' : 'text-slate-700 hover:bg-slate-100'"
        :aria-current="isActive(item.to) ? 'page' : undefined"
      >
        <span class="block text-sm" :class="isActive(item.to) ? 'font-medium' : ''">{{ t(item.key) }}</span>
        <span class="block text-xs text-slate-500 mt-0.5 leading-snug">{{ t(item.desc) }}</span>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
button:focus-visible {
  outline-offset: -2px;
}

/* same underline as the other top-level links, flush with the bar's bottom rule */
.nav-active::after {
  content: "";
  position: absolute;
  left: 0.75rem;
  right: 0.75rem;
  bottom: -1px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: theme("colors.accent.600");
}
</style>
