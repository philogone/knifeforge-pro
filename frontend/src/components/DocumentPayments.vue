<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { PaymentMethod, SalesDocument } from "@/types";

const props = defineProps<{ doc: SalesDocument }>();
const emit = defineEmits<{ (e: "update", doc: SalesDocument): void }>();

const { t, money, locale } = useI18n();
const store = useAppStore();

const methods: PaymentMethod[] = ["transfer", "card", "cheque", "cash", "other"];
const today = () => new Date().toISOString().slice(0, 10);
const form = reactive({ paid_on: today(), amount: "", method: "transfer" as PaymentMethod, reference: "" });
const adding = ref(false);
const busy = ref(false);
const error = ref("");

const n = (v: string) => Number(v);
const due = computed(() => n(props.doc.balance_due));
const refund = computed(() => props.doc.kind === "credit_note");
const parse = (v: string) => Number(String(v).replace(/[\s  ]/g, "").replace(",", "."));
const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale.value === "fr" ? "fr-FR" : "en-GB");

function open() {
  form.paid_on = today();
  form.amount = due.value.toFixed(2).replace(".", locale.value === "fr" ? "," : ".");
  form.method = "transfer";
  form.reference = "";
  error.value = "";
  adding.value = true;
}

async function save() {
  const amount = parse(form.amount);
  if (!(amount > 0)) {
    error.value = t("payments.amountInvalid");
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    emit("update", await store.addPayment(props.doc.id, { paid_on: form.paid_on, amount: amount.toFixed(2), method: form.method, reference: form.reference.trim() || null }));
    adding.value = false;
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

async function remove(id: number) {
  if (!confirm(t("payments.deleteConfirm"))) return;
  try {
    emit("update", await store.deletePayment(props.doc.id, id));
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}
</script>

<template>
  <section class="sheet p-5" aria-labelledby="payments-title">
    <div class="flex items-center justify-between gap-3 mb-3">
      <h2 id="payments-title" class="sheet-title">{{ refund ? t("payments.refundsTitle") : t("payments.title") }}</h2>
      <button v-if="due > 0 && !adding" class="btn btn-sm btn-primary" @click="open">{{ refund ? t("payments.addRefund") : t("payments.add") }}</button>
    </div>

    <dl class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
      <div>
        <dt class="text-slate-500">{{ t("payments.payable") }}</dt>
        <dd class="font-medium tabular-nums">{{ money(n(doc.amount_payable)) }}</dd>
      </div>
      <div v-if="n(doc.credited) > 0">
        <dt class="text-slate-500">{{ t("payments.credited") }}</dt>
        <dd class="font-medium tabular-nums">− {{ money(n(doc.credited)) }}</dd>
      </div>
      <div>
        <dt class="text-slate-500">{{ refund ? t("payments.refunded") : t("payments.received") }}</dt>
        <dd class="font-medium tabular-nums">{{ money(n(doc.amount_paid)) }}</dd>
      </div>
      <div>
        <dt class="text-slate-500">{{ t("payments.due") }}</dt>
        <dd class="font-semibold tabular-nums" :class="doc.overdue_days > 0 ? 'text-red-700' : due > 0 ? 'text-slate-900' : 'text-emerald-700'">
          {{ money(due) }}
          <span v-if="doc.overdue_days > 0" class="block text-xs font-normal">{{ t("payments.late", { days: doc.overdue_days }) }}</span>
        </dd>
      </div>
    </dl>

    <ul v-if="doc.prepaid_refs.length" class="mt-3 text-sm text-slate-600">
      <li v-for="r in doc.prepaid_refs" :key="r.number">{{ t("payments.depositDeducted", { number: r.number, date: fmtDate(r.date), amount: money(n(r.amount)) }) }}</li>
    </ul>

    <table v-if="doc.payments.length" class="mt-4 w-full text-sm">
      <thead>
        <tr class="text-left text-xs text-slate-500">
          <th class="font-medium pb-1">{{ t("payments.date") }}</th>
          <th class="font-medium pb-1">{{ t("payments.method") }}</th>
          <th class="font-medium pb-1">{{ t("payments.reference") }}</th>
          <th class="font-medium pb-1 text-right">{{ t("payments.amount") }}</th>
          <th class="pl-4"><span class="sr-only">{{ t("common.delete") }}</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in doc.payments" :key="p.id" class="border-t border-slate-100">
          <td class="py-1.5 tabular-nums">{{ fmtDate(p.paid_on) }}</td>
          <td class="py-1.5">{{ t(`payments.methods.${p.method}`) }}</td>
          <td class="py-1.5 text-slate-600">{{ p.reference || "—" }}</td>
          <td class="py-1.5 text-right tabular-nums whitespace-nowrap">{{ money(n(p.amount)) }}</td>
          <td class="py-1.5 pl-4 text-right">
            <button class="link-danger text-xs" :aria-label="t('payments.delete')" @click="remove(p.id)">{{ t("common.delete") }}</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="!adding" class="mt-3 text-sm text-slate-500">{{ t("payments.none") }}</p>

    <form v-if="adding" class="mt-4 rounded-lg border border-slate-200 p-3 grid gap-3 sm:grid-cols-4 items-end" @submit.prevent="save">
      <label class="block">
        <span class="field-label">{{ t("payments.date") }}</span>
        <input v-model="form.paid_on" type="date" required class="input w-full" />
      </label>
      <label class="block">
        <span class="field-label">{{ t("payments.amount") }}</span>
        <input v-model="form.amount" inputmode="decimal" required class="input w-full text-right tabular-nums" />
      </label>
      <label class="block">
        <span class="field-label">{{ t("payments.method") }}</span>
        <select v-model="form.method" class="input w-full">
          <option v-for="m in methods" :key="m" :value="m">{{ t(`payments.methods.${m}`) }}</option>
        </select>
      </label>
      <label class="block">
        <span class="field-label">{{ t("payments.reference") }}</span>
        <input v-model="form.reference" maxlength="100" class="input w-full" :placeholder="t('payments.referenceHint')" />
      </label>
      <div class="sm:col-span-4 flex flex-wrap items-center gap-2">
        <button type="submit" class="btn btn-primary" :disabled="busy">{{ t("common.save") }}</button>
        <button type="button" class="btn btn-outline" @click="adding = false">{{ t("common.cancel") }}</button>
      </div>
    </form>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-700">{{ error }}</p>
  </section>
</template>
