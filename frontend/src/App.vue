<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import { clearToken } from "@/composables/useApi";
import { useI18n } from "@/i18n";

const { t } = useI18n();
const route = useRoute();
const showChrome = computed(() => route.name !== "login");
// the editor fills the window: no footer under it
const showFooter = computed(() => showChrome.value && route.name !== "design-editor");

// the nav follows the workshop's flow: stock and know-how, then orders, then drawing
const groups: { to: string; key: string }[][] = [
  [
    { to: "/", key: "nav.materials" },
    { to: "/treatments", key: "nav.recipes" },
    { to: "/knife-models", key: "nav.knifeModels" },
  ],
  [
    { to: "/orders", key: "nav.orders" },
    { to: "/production", key: "nav.production" },
  ],
  [
    { to: "/designs", key: "nav.designs" },
    { to: "/nesting", key: "nav.nesting" },
  ],
];

/** a detail page (/orders/3, /designs/1) keeps its section lit */
function isActive(to: string): boolean {
  if (to === "/") return route.path === "/";
  return route.path === to || route.path.startsWith(`${to}/`);
}

function logout() {
  clearToken();
  window.location.href = "/login";
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 bench">
    <a v-if="showChrome" href="#main" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-1.5 btn btn-primary">{{ t("nav.skip") }}</a>
    <nav v-if="showChrome" class="h-14 bg-white/95 border-b border-slate-200 px-5 flex items-center gap-6 sticky top-0 z-40">
      <router-link to="/" class="flex items-center gap-2 shrink-0 text-slate-900" :aria-label="t('app.title')">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" class="fill-accent-600" />
          <path d="M4 14h11l2-3h7c3 0 5 2 6 5-2 3-5 5-9 5h-4l-2-3H4z" class="fill-accent-100" />
        </svg>
        <span class="font-semibold tracking-tight">KnifeForge <span class="text-accent-700">Pro</span></span>
      </router-link>

      <div class="flex items-center h-full min-w-0 overflow-x-auto">
        <template v-for="(group, gi) in groups" :key="gi">
          <span v-if="gi" class="mx-2 h-4 w-px bg-slate-200 shrink-0" aria-hidden="true"></span>
          <router-link
            v-for="item in group"
            :key="item.to"
            :to="item.to"
            class="relative h-full px-2.5 flex items-center text-sm whitespace-nowrap transition-colors"
            :class="isActive(item.to) ? 'text-slate-900 font-medium nav-active' : 'text-slate-600 hover:text-slate-900'"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            {{ t(item.key) }}
          </router-link>
        </template>
      </div>

      <div class="ml-auto flex items-center gap-4 shrink-0 text-sm">
        <router-link
          to="/settings"
          class="relative h-14 px-2.5 flex items-center"
          :class="isActive('/settings') ? 'text-slate-900 font-medium nav-active' : 'text-slate-600 hover:text-slate-900'"
          :aria-current="isActive('/settings') ? 'page' : undefined"
        >
          {{ t("nav.settings") }}
        </router-link>
        <button class="text-slate-500 hover:text-slate-900" @click="logout">{{ t("nav.signOut") }}</button>
      </div>
    </nav>
    <main id="main" tabindex="-1" class="outline-none"><router-view /></main>
    <p v-if="showFooter" class="text-center text-xs text-slate-500 py-10">{{ t("app.footer") }}</p>
  </div>
</template>

<style scoped>
/* the link strip scrolls horizontally, which clips an outside ring: draw it inside */
nav a:focus-visible {
  outline-offset: -2px;
}

/* the active section is underlined in the action colour, flush with the bar's bottom rule */
.nav-active::after {
  content: "";
  position: absolute;
  left: 0.625rem;
  right: 0.625rem;
  bottom: -1px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: theme("colors.accent.600");
}
</style>
