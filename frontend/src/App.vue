<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import NavMenu, { type NavItem } from "@/components/NavMenu.vue";
import { clearToken } from "@/composables/useApi";
import { useTheme } from "@/composables/useTheme";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";

const { t } = useI18n();
const theme = useTheme();
const route = useRoute();
const store = useAppStore();
// public demo: a band says the data is invented and nothing is saved
const demo = ref(false);
onMounted(async () => {
  try {
    demo.value = !!(await store.authStatus()).demo;
  } catch {
    // no server yet: the pages say so themselves
  }
});
const showChrome = computed(() => route.name !== "login");
// the editor fills the window: no footer under it
const showFooter = computed(() => showChrome.value && route.name !== "design-editor");

// three sections, each a menu: the workshop (stock and know-how), drawing and cutting, sales
const groups: { label: string; items: NavItem[] }[] = [
  {
    label: "nav.group.workshop",
    items: [
      { to: "/production", key: "nav.production", desc: "nav.desc.production" },
      { to: "/materials", key: "nav.materials", desc: "nav.desc.materials" },
      { to: "/treatments", key: "nav.recipes", desc: "nav.desc.recipes" },
      { to: "/knife-models", key: "nav.knifeModels", desc: "nav.desc.knifeModels" },
    ],
  },
  {
    label: "nav.group.design",
    items: [
      { to: "/designs", key: "nav.designs", desc: "nav.desc.designs" },
      { to: "/nesting", key: "nav.nesting", desc: "nav.desc.nesting" },
      { to: "/calibration", key: "nav.calibration", desc: "nav.desc.calibration" },
    ],
  },
  {
    label: "nav.group.sales",
    items: [
      { to: "/customers", key: "nav.customers", desc: "nav.desc.customers" },
      { to: "/orders", key: "nav.orders", desc: "nav.desc.orders" },
      { to: "/documents", key: "nav.documents", desc: "nav.desc.documents" },
      { to: "/accounting", key: "nav.accounting", desc: "nav.desc.accounting" },
    ],
  },
];

/** a detail page (/orders/3, /designs/1) keeps its section lit */
function isActive(to: string): boolean {
  if (to === "/") return route.path === "/";
  return route.path === to || route.path.startsWith(`${to}/`);
}

// below lg the sections fold into one panel opened from a Menu button
const mobileOpen = ref(false);
watch(() => route.fullPath, () => (mobileOpen.value = false));

function logout() {
  clearToken();
  window.location.href = "/login";
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 bench">
    <a v-if="showChrome" href="#main" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-1.5 btn btn-primary">{{ t("nav.skip") }}</a>
    <nav v-if="showChrome" class="h-14 bg-paper/95 border-b border-slate-200 px-5 flex items-center gap-6 sticky top-0 z-40">
      <router-link to="/" class="flex items-center gap-2 shrink-0 text-slate-900" :aria-label="t('app.title')">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" class="fill-accent-600" />
          <path d="M4 14h11l2-3h7c3 0 5 2 6 5-2 3-5 5-9 5h-4l-2-3H4z" class="fill-accent-100" />
        </svg>
        <span class="font-semibold tracking-tight">KnifeForge <span class="text-accent-700">Pro</span></span>
      </router-link>

      <div class="hidden lg:flex items-center h-full min-w-0">
        <router-link
          to="/"
          class="relative h-full px-3 flex items-center text-sm whitespace-nowrap transition-colors"
          :class="isActive('/') ? 'text-slate-900 font-medium nav-active' : 'text-slate-600 hover:text-slate-900'"
          :aria-current="isActive('/') ? 'page' : undefined"
        >
          {{ t("nav.dashboard") }}
        </router-link>
        <NavMenu v-for="g in groups" :key="g.label" :label="t(g.label)" :items="g.items" />
      </div>

      <button
        type="button"
        class="lg:hidden ml-auto btn btn-outline btn-sm"
        :aria-expanded="mobileOpen"
        aria-controls="mobile-nav"
        @click="mobileOpen = !mobileOpen"
      >
        {{ mobileOpen ? t("nav.close") : t("nav.menu") }}
      </button>

      <div class="hidden lg:flex ml-auto items-center gap-4 shrink-0 text-sm">
        <router-link
          to="/settings"
          class="relative h-14 px-3 flex items-center"
          :class="isActive('/settings') ? 'text-slate-900 font-medium nav-active' : 'text-slate-600 hover:text-slate-900'"
          :aria-current="isActive('/settings') ? 'page' : undefined"
        >
          {{ t("nav.settings") }}
        </router-link>
        <button
          class="p-1.5 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100"
          :title="theme.isDark.value ? t('theme.toLight') : t('theme.toDark')"
          :aria-label="theme.isDark.value ? t('theme.toLight') : t('theme.toDark')"
          @click="theme.toggle()"
        >
          <svg v-if="theme.isDark.value" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
            <circle cx="10" cy="10" r="3.5" /><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M4.3 15.7l1.4-1.4M14.3 5.7l1.4-1.4" />
          </svg>
          <svg v-else width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" aria-hidden="true">
            <path d="M16.5 12.5A7 7 0 0 1 7.5 3.5a7 7 0 1 0 9 9z" />
          </svg>
        </button>
        <button class="text-slate-500 hover:text-slate-900" @click="logout">{{ t("nav.signOut") }}</button>
      </div>
      <div v-if="mobileOpen" id="mobile-nav" class="lg:hidden absolute inset-x-0 top-full border-b border-slate-200 bg-paper shadow-lg max-h-[calc(100vh-3.5rem)] overflow-y-auto">
        <div class="px-5 py-3 space-y-4 text-sm">
          <router-link to="/" class="block py-1.5" :class="isActive('/') ? 'font-medium text-accent-800' : 'text-slate-700'">{{ t("nav.dashboard") }}</router-link>
          <div v-for="g in groups" :key="g.label">
            <p class="text-xs font-medium text-slate-500">{{ t(g.label) }}</p>
            <router-link
              v-for="item in g.items"
              :key="item.to"
              :to="item.to"
              class="block py-1.5"
              :class="isActive(item.to) ? 'font-medium text-accent-800' : 'text-slate-700'"
              :aria-current="isActive(item.to) ? 'page' : undefined"
            >
              {{ t(item.key) }}
            </router-link>
          </div>
          <div class="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-4">
            <router-link to="/settings" class="py-1.5" :class="isActive('/settings') ? 'font-medium text-accent-800' : 'text-slate-700'">{{ t("nav.settings") }}</router-link>
            <button class="py-1.5 text-slate-700" @click="theme.toggle()">{{ theme.isDark.value ? t("theme.toLight") : t("theme.toDark") }}</button>
            <button class="py-1.5 text-slate-500" @click="logout">{{ t("nav.signOut") }}</button>
          </div>
        </div>
      </div>
    </nav>
    <p v-if="demo && showChrome" class="px-5 py-2 text-center text-sm bg-amber-50 text-amber-900 border-b border-amber-200" role="status">
      {{ t("demo.band") }}
    </p>
    <main id="main" tabindex="-1" class="outline-none"><router-view /></main>
    <p v-if="showFooter" class="text-center text-xs text-slate-500 py-10">{{ t("app.footer") }}</p>
  </div>
</template>

<style scoped>
/* links fill the bar's height: draw the focus ring inside so the bar does not clip it */
nav a:focus-visible {
  outline-offset: -2px;
}

/* the active section is underlined in the action colour, flush with the bar's bottom rule */
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
