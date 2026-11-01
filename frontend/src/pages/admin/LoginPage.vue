<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
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
    error.value = err instanceof ApiError ? String(err.detail) : t("login.failed");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="max-w-sm mx-auto mt-24 px-4">
    <h1 class="text-2xl font-bold text-slate-900 text-center mb-6">{{ t("login.title") }}</h1>
    <form class="space-y-4" @submit.prevent="submit">
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("login.email") }}</label>
        <input v-model="email" type="email" required class="w-full rounded-lg border border-slate-300 px-3 py-2" />
      </div>
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("login.password") }}</label>
        <input v-model="password" type="password" required class="w-full rounded-lg border border-slate-300 px-3 py-2" />
      </div>
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      <button type="submit" :disabled="loading" class="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium rounded-lg py-2">
        {{ t("login.signIn") }}
      </button>
    </form>
  </div>
</template>
