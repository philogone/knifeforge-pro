<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

const { t } = useI18n();
const store = useAppStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    await store.login(email.value, password.value);
    router.push("/");
  } catch (err) {
    error.value = errorMessage(err, t, "login.failed");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="min-h-screen grid lg:grid-cols-[1.15fr_1fr]">
    <!-- the drawing board: a blade plate, drawn the way the editor draws it -->
    <section class="relative hidden lg:flex flex-col justify-between p-10 border-r border-slate-200 bg-paper/60" aria-hidden="true">
      <div class="flex items-center gap-2 text-slate-900">
        <svg width="28" height="28" viewBox="0 0 32 32">
          <rect width="32" height="32" rx="7" class="fill-accent-600" />
          <path d="M4 14h11l2-3h7c3 0 5 2 6 5-2 3-5 5-9 5h-4l-2-3H4z" class="fill-accent-100" />
        </svg>
        <span class="font-semibold tracking-tight">KnifeForge <span class="text-accent-700">Pro</span></span>
      </div>

      <svg viewBox="0 0 700 300" class="w-full max-w-2xl mx-auto drawing text-slate-900" fill="none">
        <!-- blade -->
        <path
          class="draw"
          d="M40 120 H250 L272 98 H470 C520 98 560 112 600 150 C560 196 500 206 430 206 H272 L250 180 H40 Z"
          stroke="currentColor" stroke-width="1.6" fill="rgb(var(--slate-500) / 0.10)"
        />
        <!-- grind line, dash-dot -->
        <path class="fade" d="M300 160 C400 150 500 150 596 150" stroke="#0f766e" stroke-width="1.2" stroke-dasharray="9 3 2 3" />
        <!-- holes -->
        <circle class="fade" cx="95" cy="150" r="9" stroke="#dc2626" stroke-width="1.4" fill="rgb(var(--paper))" />
        <circle class="fade" cx="175" cy="150" r="9" stroke="#dc2626" stroke-width="1.4" fill="rgb(var(--paper))" />
        <!-- overall length -->
        <g class="fade" stroke="rgb(var(--slate-600))" stroke-width="1">
          <path d="M40 186 V262 M600 156 V262" stroke-dasharray="2 3" />
          <path d="M40 250 H600" />
          <path d="M40 250 l10 -4 v8 z M600 250 l-10 -4 v8 z" fill="rgb(var(--slate-600))" />
        </g>
        <text class="fade" x="320" y="240" text-anchor="middle" font-size="15" fill="currentColor" font-family="IBM Plex Sans, sans-serif">182,0 mm</text>
        <!-- blade height -->
        <g class="fade" stroke="rgb(var(--slate-600))" stroke-width="1">
          <path d="M470 98 H628 M430 206 H628" stroke-dasharray="2 3" />
          <path d="M618 98 V206" />
          <path d="M618 98 l-4 10 h8 z M618 206 l-4 -10 h8 z" fill="rgb(var(--slate-600))" />
        </g>
        <text class="fade" x="632" y="157" font-size="14" fill="currentColor" font-family="IBM Plex Sans, sans-serif">32,0</text>
      </svg>

      <div>
        <p class="text-2xl font-semibold tracking-tight text-slate-900 max-w-md leading-snug">{{ t("login.tagline") }}</p>
        <p class="mt-2 text-sm text-slate-600 max-w-md">{{ t("login.sub") }}</p>
      </div>
    </section>

    <section class="flex items-center justify-center p-6">
      <div class="w-full max-w-sm">
        <div class="lg:hidden flex items-center gap-2 mb-8 text-slate-900">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="7" class="fill-accent-600" />
            <path d="M4 14h11l2-3h7c3 0 5 2 6 5-2 3-5 5-9 5h-4l-2-3H4z" class="fill-accent-100" />
          </svg>
          <span class="font-semibold tracking-tight">KnifeForge <span class="text-accent-700">Pro</span></span>
        </div>
        <h1 class="page-title">{{ t("login.title") }}</h1>
        <p class="page-lead mb-8">{{ t("login.lead") }}</p>
        <form class="space-y-4" @submit.prevent="submit">
          <label class="block">
            <span class="field-label">{{ t("login.email") }}</span>
            <input v-model="email" type="email" autocomplete="username" required class="input w-full" />
          </label>
          <label class="block">
            <span class="field-label">{{ t("login.password") }}</span>
            <input v-model="password" type="password" autocomplete="current-password" required class="input w-full" />
          </label>
          <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
          <button type="submit" :disabled="loading" class="btn btn-primary w-full py-2.5">
            {{ loading ? t("login.signingIn") : t("login.signIn") }}
          </button>
        </form>
      </div>
    </section>
  </main>
</template>

<style scoped>
/* one authored moment: the plate draws itself, then the annotations settle in */
.drawing .draw {
  stroke-dasharray: 1600;
  stroke-dashoffset: 1600;
  animation: draw 1.6s cubic-bezier(0.16, 1, 0.3, 1) 0.15s forwards;
}
.drawing .fade {
  opacity: 0;
  animation: fade 0.6s ease-out 1.1s forwards;
}
@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes fade {
  to {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .drawing .draw,
  .drawing .fade {
    animation: none;
    stroke-dashoffset: 0;
    opacity: 1;
  }
}
</style>
