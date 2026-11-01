<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import { clearToken } from "@/composables/useApi";
import { useI18n } from "@/i18n";

const { t } = useI18n();
const route = useRoute();
const showChrome = computed(() => route.name !== "login");

function logout() {
  clearToken();
  window.location.href = "/login";
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <nav v-if="showChrome" class="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between flex-wrap gap-2">
      <div class="flex items-center gap-6 flex-wrap">
        <router-link to="/" class="font-bold text-lg text-slate-900">{{ t("app.title") }}</router-link>
        <router-link to="/" class="text-sm text-slate-600 hover:text-slate-900" active-class="text-indigo-600 font-medium">{{ t("nav.materials") }}</router-link>
        <router-link to="/knife-models" class="text-sm text-slate-600 hover:text-slate-900" active-class="text-indigo-600 font-medium">{{ t("nav.knifeModels") }}</router-link>
        <router-link to="/treatments" class="text-sm text-slate-600 hover:text-slate-900" active-class="text-indigo-600 font-medium">{{ t("nav.recipes") }}</router-link>
        <router-link to="/orders" class="text-sm text-slate-600 hover:text-slate-900" active-class="text-indigo-600 font-medium">{{ t("nav.orders") }}</router-link>
        <router-link to="/production" class="text-sm text-slate-600 hover:text-slate-900" active-class="text-indigo-600 font-medium">{{ t("nav.production") }}</router-link>
        <router-link to="/settings" class="text-sm text-slate-600 hover:text-slate-900" active-class="text-indigo-600 font-medium">{{ t("nav.settings") }}</router-link>
      </div>
      <button class="text-sm text-slate-500 hover:text-slate-800" @click="logout">{{ t("nav.signOut") }}</button>
    </nav>
    <router-view />
    <p class="text-center text-xs text-slate-400 py-8">{{ t("app.footer") }}</p>
  </div>
</template>
