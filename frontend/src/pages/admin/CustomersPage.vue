<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import ListToolbar from "@/components/ListToolbar.vue";
import { byText, useListSearch } from "@/composables/useListSearch";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { Customer } from "@/types";

const { t } = useI18n();
const store = useAppStore();

const customers = ref<Customer[]>([]);
const loading = ref(true);
const error = ref("");
const showForm = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const formError = ref("");

const empty = () => ({
  is_business: false,
  name: "",
  company_name: "",
  email: "",
  phone: "",
  address_line1: "",
  address_line2: "",
  postal_code: "",
  city: "",
  country: "FR",
  delivery_line1: "",
  delivery_postal_code: "",
  delivery_city: "",
  siren: "",
  vat_number: "",
  notes: "",
});
const form = reactive(empty());
const otherDelivery = ref(false);

async function load() {
  try {
    customers.value = await store.fetchCustomers();
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function startNew() {
  Object.assign(form, empty());
  otherDelivery.value = false;
  editingId.value = null;
  showForm.value = true;
}

function startEdit(c: Customer) {
  Object.assign(form, empty());
  for (const key of Object.keys(form) as (keyof typeof form)[]) {
    const value = c[key as keyof Customer];
    (form as Record<string, unknown>)[key] = value ?? (typeof form[key] === "boolean" ? false : "");
  }
  otherDelivery.value = !!c.delivery_line1;
  editingId.value = c.id;
  showForm.value = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function cancel() {
  showForm.value = false;
  editingId.value = null;
}

async function submit() {
  if (saving.value) return;
  saving.value = true;
  formError.value = "";
  const payload: Record<string, unknown> = { ...form };
  if (!otherDelivery.value) {
    payload.delivery_line1 = payload.delivery_postal_code = payload.delivery_city = null;
  }
  for (const [k, v] of Object.entries(payload)) if (v === "") payload[k] = null;
  payload.country = form.country || "FR";
  try {
    await store.saveCustomer(payload as Partial<Customer>, editingId.value ?? undefined);
    cancel();
    await load();
  } catch (err) {
    formError.value = errorMessage(err, t);
  } finally {
    saving.value = false;
  }
}

function displayName(c: Customer) {
  return c.is_business && c.company_name ? c.company_name : c.name;
}

async function exportOne(c: Customer) {
  const data = await store.exportCustomer(c.id);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: `client-${c.id}-donnees.json` });
  a.click();
  URL.revokeObjectURL(url);
}

async function remove(c: Customer) {
  error.value = "";
  if (c.order_count || c.document_count) {
    if (!confirm(t("customers.eraseConfirm", { name: displayName(c) }))) return;
    try {
      await store.eraseCustomer(c.id);
    } catch (err) {
      error.value = errorMessage(err, t);
    }
  } else {
    if (!confirm(t("common.confirmDeleteNamed", { name: displayName(c) }))) return;
    try {
      await store.deleteCustomer(c.id);
    } catch (err) {
      error.value = errorMessage(err, t);
    }
  }
  await load();
}

const list = useListSearch(
  () => customers.value,
  (c) => [c.name, c.company_name, c.email, c.phone, c.city, c.siren],
  [
    { key: "name", label: "", compare: (a, b) => byText(displayName(a), displayName(b)) },
    { key: "recent", label: "", compare: (a, b) => b.created_at.localeCompare(a.created_at) },
  ],
);
const sortOptions = computed(() => [
  { key: "name", label: t("list.sort.name") },
  { key: "recent", label: t("list.sort.recent") },
]);
</script>

<template>
  <div class="page max-w-4xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("customers.title") }}</h1>
        <p class="page-lead">{{ t("customers.lead") }}</p>
      </div>
      <button v-if="!showForm" class="btn btn-primary" @click="startNew">+ {{ t("customers.add") }}</button>
    </header>
    <p v-if="error" role="alert" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <form v-if="showForm" class="sheet p-5 mb-8 space-y-4" @submit.prevent="submit">
      <h2 class="sheet-title">{{ editingId ? t("customers.edit") : t("customers.add") }}</h2>
      <div class="flex gap-2" role="radiogroup">
        <button
          v-for="b in [false, true]"
          :key="String(b)"
          type="button"
          role="radio"
          :aria-checked="form.is_business === b"
          class="btn btn-sm border"
          :class="form.is_business === b ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="form.is_business = b"
        >
          {{ b ? t("customers.business") : t("customers.person") }}
        </button>
      </div>
      <div class="field-grid grid grid-cols-2 gap-3">
        <div v-if="form.is_business" class="col-span-2">
          <label class="field-label" for="cu-company">{{ t("customers.companyName") }}</label>
          <input id="cu-company" v-model="form.company_name" required class="input w-full" />
        </div>
        <div>
          <label class="field-label" for="cu-name">{{ form.is_business ? t("customers.contactName") : t("customers.name") }}</label>
          <input id="cu-name" v-model="form.name" required class="input w-full" autocomplete="name" />
        </div>
        <div>
          <label class="field-label" for="cu-email">{{ t("customers.email") }}</label>
          <input id="cu-email" v-model="form.email" type="email" class="input w-full" autocomplete="email" />
        </div>
        <div>
          <label class="field-label" for="cu-phone">{{ t("customers.phone") }}</label>
          <input id="cu-phone" v-model="form.phone" class="input w-full" autocomplete="tel" />
        </div>
        <div v-if="form.is_business">
          <label class="field-label" for="cu-siren">{{ t("customers.siren") }}</label>
          <input id="cu-siren" v-model="form.siren" inputmode="numeric" pattern="\d{9}" maxlength="9" class="input w-full" :placeholder="t('customers.sirenHint')" />
        </div>
        <div class="col-span-2">
          <label class="field-label" for="cu-addr">{{ t("customers.address") }}</label>
          <input id="cu-addr" v-model="form.address_line1" class="input w-full" autocomplete="address-line1" />
        </div>
        <div>
          <label class="field-label" for="cu-pc">{{ t("customers.postalCode") }}</label>
          <input id="cu-pc" v-model="form.postal_code" class="input w-full" autocomplete="postal-code" />
        </div>
        <div>
          <label class="field-label" for="cu-city">{{ t("customers.city") }}</label>
          <input id="cu-city" v-model="form.city" class="input w-full" autocomplete="address-level2" />
        </div>
        <div v-if="form.is_business">
          <label class="field-label" for="cu-vat">{{ t("customers.vatNumber") }}</label>
          <input id="cu-vat" v-model="form.vat_number" class="input w-full" />
        </div>
        <div>
          <label class="field-label" for="cu-country">{{ t("customers.country") }}</label>
          <input id="cu-country" v-model="form.country" maxlength="2" class="input w-full uppercase" />
        </div>
      </div>
      <label class="flex items-center gap-2 text-sm text-slate-700">
        <input v-model="otherDelivery" type="checkbox" /> {{ t("customers.otherDelivery") }}
      </label>
      <div v-if="otherDelivery" class="field-grid grid grid-cols-2 gap-3">
        <div class="col-span-2">
          <label class="field-label" for="cu-dl">{{ t("customers.deliveryAddress") }}</label>
          <input id="cu-dl" v-model="form.delivery_line1" class="input w-full" />
        </div>
        <div>
          <label class="field-label" for="cu-dpc">{{ t("customers.postalCode") }}</label>
          <input id="cu-dpc" v-model="form.delivery_postal_code" class="input w-full" />
        </div>
        <div>
          <label class="field-label" for="cu-dcity">{{ t("customers.city") }}</label>
          <input id="cu-dcity" v-model="form.delivery_city" class="input w-full" />
        </div>
      </div>
      <div>
        <label class="field-label" for="cu-notes">{{ t("common.notes") }}</label>
        <textarea id="cu-notes" v-model="form.notes" rows="2" class="input w-full"></textarea>
      </div>
      <p v-if="formError" role="alert" class="text-sm text-red-700">{{ formError }}</p>
      <div class="flex gap-2">
        <button type="submit" class="btn btn-primary" :disabled="saving">{{ editingId ? t("common.saveChanges") : t("customers.add") }}</button>
        <button type="button" class="btn btn-outline" @click="cancel">{{ t("common.cancel") }}</button>
      </div>
    </form>

    <ListToolbar
      v-if="list.total.value"
      v-model:query="list.query.value"
      v-model:sort="list.sortKey.value"
      :placeholder="t('customers.search')"
      :sorts="sortOptions"
      :shown="list.visible.value.length"
      :total="list.total.value"
    />
    <p v-if="loading" class="text-sm text-slate-500">{{ t("common.loading") }}</p>
    <p v-else-if="!customers.length" class="sheet p-6 text-sm text-slate-600">{{ t("customers.empty") }}</p>
    <p v-else-if="!list.visible.value.length" class="sheet p-6 text-sm text-slate-600">{{ t("list.noMatch") }}</p>

    <div class="space-y-3">
      <article v-for="c in list.visible.value" :key="c.id" class="sheet p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-2 flex-wrap min-w-0">
            <span class="font-semibold text-slate-900">{{ displayName(c) }}</span>
            <span class="tag" :class="c.is_business ? 'tag-info' : 'tag-neutral'">{{ c.is_business ? t("customers.business") : t("customers.person") }}</span>
            <span v-if="c.anonymized_at" class="tag tag-warning">{{ t("customers.erased") }}</span>
          </div>
          <div v-if="!c.anonymized_at" class="flex gap-4 shrink-0">
            <button class="link-action" @click="startEdit(c)">{{ t("common.edit") }}</button>
            <button class="link-danger" @click="remove(c)">{{ c.order_count || c.document_count ? t("customers.erase") : t("common.delete") }}</button>
          </div>
        </div>
        <p class="mt-1 text-sm text-slate-600">
          {{ [c.is_business && c.company_name ? c.name : null, c.email, c.phone, [c.postal_code, c.city].filter(Boolean).join(" ")].filter(Boolean).join(" · ") }}
        </p>
        <div class="mt-3 pt-3 border-t border-slate-100 flex items-center gap-5 flex-wrap text-sm">
          <router-link :to="{ path: '/orders', query: { customer: String(c.id) } }" class="link-action">{{ t("customers.orders", { n: c.order_count }) }}</router-link>
          <router-link :to="{ path: '/documents', query: { customer: String(c.id) } }" class="link-action">{{ t("customers.documents", { n: c.document_count }) }}</router-link>
          <button v-if="!c.anonymized_at" class="link-action ml-auto" @click="exportOne(c)">{{ t("customers.export") }}</button>
        </div>
      </article>
    </div>
  </div>
</template>
