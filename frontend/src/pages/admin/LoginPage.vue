<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import AppLogo from "@/components/AppLogo.vue";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

const { t } = useI18n();
const store = useAppStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const confirm = ref("");
const error = ref("");
const loading = ref(false);
// first launch of the desktop build: the account is created here instead of signing in
const setup = ref(false);
// public demo: no account, one button
const demo = ref(false);

onMounted(async () => {
  try {
    const status = await store.authStatus();
    setup.value = status.needs_setup;
    demo.value = !!status.demo;
  } catch {
    // older server or no network: the sign-in form reports the problem on submit
  }
});

async function enterDemo() {
  error.value = "";
  loading.value = true;
  try {
    await store.enterDemo();
    router.push("/");
  } catch (err) {
    error.value = errorMessage(err, t, "login.failed");
  } finally {
    loading.value = false;
  }
}

async function submit() {
  error.value = "";
  if (setup.value && password.value !== confirm.value) {
    error.value = t("setup.mismatch");
    return;
  }
  loading.value = true;
  try {
    if (setup.value) await store.setupAccount(email.value.trim(), password.value);
    else await store.login(email.value, password.value);
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
    <!-- the drawing board: the library drop point (default parameters), drawn the way the editor draws it -->
    <section class="relative hidden lg:flex flex-col justify-between p-10 border-r border-slate-200 bg-paper/60" aria-hidden="true">
      <div class="flex items-center gap-2 text-slate-900">
        <AppLogo :size="28" />
        <span class="font-semibold tracking-tight">KnifeForge <span class="text-accent-700">Pro</span></span>
      </div>

      <svg viewBox="0 0 700 300" class="w-full max-w-2xl mx-auto drawing text-slate-900" fill="none">
        <!-- blade -->
        <path
          class="draw"
          d="M307.8 100 C307.8 100 467.7 100 467.7 100 C524.8 100 562.5 117.6 593.3 132.6 C557 159 519.1 181.6 450.6 181.6 C450.6 181.6 326.7 181.6 326.7 181.6 C326.7 178 323.8 175.1 320.2 175.1 C316.5 175.1 313.6 178 313.6 181.6 C313.6 184.9 310.1 186.1 305.4 186.1 C296 186.1 286.6 158.1 265.4 158.1 C222.6 158.1 184.6 165.5 136.4 165.5 C82.8 165.5 88.2 162.9 56.1 162.9 C45.4 162.9 40 151.4 40 131.8 C40 113.5 45.4 102.4 56.1 102.4 C123 102.4 307.8 100 307.8 100Z"
          stroke="currentColor" stroke-width="1.6" fill="rgb(var(--slate-500) / 0.10)"
        />
        <!-- grind line, dash-dot -->
        <path class="fade" d="M329.2 181.6 C329.2 181.6 344.5 165.3 354.7 140.8 C354.7 140.8 489.8 140.8 489.8 140.8 C489.8 140.8 549.4 135.1 588.3 132.6" stroke="#0f766e" stroke-width="1.2" stroke-dasharray="9 3 2 3" />
        <!-- holes -->
        <circle class="fade" cx="93.6" cy="130.6" r="6.4" stroke="#dc2626" stroke-width="1.4" fill="rgb(var(--paper))" />
        <circle class="fade" cx="252.7" cy="130.6" r="6.4" stroke="#dc2626" stroke-width="1.4" fill="rgb(var(--paper))" />
        <!-- overall length -->
        <g class="fade" stroke="rgb(var(--slate-600))" stroke-width="1">
          <path d="M40 170 V262 M593.3 138 V262" stroke-dasharray="2 3" />
          <path d="M40 250 H593.3" />
          <path d="M40 250 l10 -4 v8 z M593.3 250 l-10 -4 v8 z" fill="rgb(var(--slate-600))" />
        </g>
        <text class="fade" x="320" y="240" text-anchor="middle" font-size="15" fill="currentColor" font-family="IBM Plex Sans, sans-serif">217,0 mm</text>
        <!-- blade height -->
        <g class="fade" stroke="rgb(var(--slate-600))" stroke-width="1">
          <path d="M470 100 H628 M452 181.6 H628" stroke-dasharray="2 3" />
          <path d="M618 100 V181.6" />
          <path d="M618 100 l-4 10 h8 z M618 181.6 l-4 -10 h8 z" fill="rgb(var(--slate-600))" />
        </g>
        <text class="fade" x="632" y="146" font-size="14" fill="currentColor" font-family="IBM Plex Sans, sans-serif">32,0</text>
      </svg>

      <div>
        <p class="text-2xl font-semibold tracking-tight text-slate-900 max-w-md leading-snug">{{ t("login.tagline") }}</p>
        <p class="mt-2 text-sm text-slate-600 max-w-md">{{ t("login.sub") }}</p>
      </div>
    </section>

    <section class="flex items-center justify-center p-6">
      <div class="w-full max-w-sm">
        <div class="lg:hidden flex items-center gap-2 mb-8 text-slate-900">
          <AppLogo :size="28" />
          <span class="font-semibold tracking-tight">KnifeForge <span class="text-accent-700">Pro</span></span>
        </div>
        <template v-if="demo">
          <h1 class="page-title">{{ t("demo.title") }}</h1>
          <p class="page-lead mb-8">{{ t("demo.lead") }}</p>
          <p v-if="error" role="alert" class="mb-4 text-sm text-red-700">{{ error }}</p>
          <button type="button" :disabled="loading" class="btn btn-primary w-full py-2.5" @click="enterDemo">{{ t("demo.enter") }}</button>
        </template>
        <template v-else>
        <h1 class="page-title">{{ setup ? t("setup.title") : t("login.title") }}</h1>
        <p class="page-lead mb-8">{{ setup ? t("setup.lead") : t("login.lead") }}</p>
        <form class="space-y-4" @submit.prevent="submit">
          <label class="block">
            <span class="field-label">{{ t("login.email") }}</span>
            <input v-model="email" type="email" autocomplete="username" required class="input w-full" />
          </label>
          <label class="block">
            <span class="field-label">{{ t("login.password") }}</span>
            <input
              v-model="password"
              type="password"
              :autocomplete="setup ? 'new-password' : 'current-password'"
              :minlength="setup ? 10 : undefined"
              :maxlength="setup ? 72 : undefined"
              required
              class="input w-full"
              :aria-describedby="setup ? 'setup-hint' : undefined"
            />
          </label>
          <p v-if="setup" id="setup-hint" class="sheet-hint -mt-2">{{ t("setup.passwordHint") }}</p>
          <p v-if="setup" class="sheet-hint">{{ t("setup.restoreHint") }}</p>
          <label v-if="setup" class="block">
            <span class="field-label">{{ t("setup.confirm") }}</span>
            <input v-model="confirm" type="password" autocomplete="new-password" required class="input w-full" />
          </label>
          <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
          <button type="submit" :disabled="loading" class="btn btn-primary w-full py-2.5">
            {{ loading ? t("login.signingIn") : setup ? t("setup.create") : t("login.signIn") }}
          </button>
        </form>
        </template>
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
