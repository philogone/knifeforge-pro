<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import DocumentHistory from "@/components/DocumentHistory.vue";
import DocumentMailDialog from "@/components/DocumentMailDialog.vue";
import DocumentPayments from "@/components/DocumentPayments.vue";
import EditorIcon from "@/components/EditorIcon.vue";
import { saveBlob } from "@/composables/useApi";
import { DOCUMENT_STATUS_TAG } from "@/constants/referenceData";
import { formatDecimal, formatFixed, useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { Customer, DocumentLine, MailPurpose, OperationNature, SalesDocument, ShopSettings } from "@/types";

const { t, money, locale } = useI18n();
const store = useAppStore();
const route = useRoute();
const router = useRouter();

const doc = ref<SalesDocument | null>(null);
const customers = ref<Customer[]>([]);
const shop = ref<ShopSettings | null>(null);
const busy = ref(false);
const error = ref("");
const saved = ref(false);

const form = reactive({
  customer_id: null as number | null,
  nature: "goods" as OperationNature,
  vat_on_debits: false,
  delivery_date: "" as string,
  notes: "",
  lines: [] as DocumentLine[],
});

const editable = computed(() => doc.value?.status === "draft");
const franchise = computed(() => (shop.value?.vat_regime ?? "franchise") === "franchise");
const defaultRate = computed(() => (franchise.value ? "0" : String(shop.value?.default_vat_rate ?? 20)));

function fill(d: SalesDocument) {
  doc.value = d;
  form.customer_id = d.customer_id;
  form.nature = d.nature;
  form.vat_on_debits = d.vat_on_debits;
  form.delivery_date = d.delivery_date ?? "";
  form.notes = d.notes ?? "";
  // decimals arrive as "2.000" / "180.00": show them the way the reader writes them
  form.lines = d.lines.map((l) => ({
    ...l,
    quantity: formatDecimal(Number(l.quantity), locale.value, 3),
    unit_price_ht: formatFixed(Number(l.unit_price_ht), locale.value, 2),
    vat_rate: formatDecimal(Number(l.vat_rate), locale.value, 2),
  }));
}

onMounted(async () => {
  const id = Number(route.params.id);
  try {
    const [d, cs, s] = await Promise.all([store.fetchDocument(id), store.fetchCustomers(), store.fetchShopSettings()]);
    customers.value = cs.filter((c) => !c.anonymized_at || c.id === d.customer_id);
    shop.value = s;
    fill(d);
    // from the list of overdue invoices: open the reminder straight away
    if (route.query.remind && canRemind.value) mail.value = nextLevel.value;
  } catch (err) {
    error.value = errorMessage(err, t);
  }
});

// live totals, computed the same way as the server (per VAT rate, rounded to the cent)
const round2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100;
/** "1 234,50" or "1234.5" -> 1234.5 */
const parseNum = (v: string | number) => Number(String(v ?? "").replace(/[\s  ]/g, "").replace(",", ".")) || 0;
const lineTotal = (l: DocumentLine) => round2(parseNum(l.quantity) * parseNum(l.unit_price_ht));
const totals = computed(() => {
  const bases = new Map<number, number>();
  for (const l of form.lines) bases.set(parseNum(l.vat_rate), (bases.get(parseNum(l.vat_rate)) ?? 0) + lineTotal(l));
  let ht = 0;
  let vat = 0;
  const rows = [...bases.entries()].sort((a, b) => a[0] - b[0]).map(([rate, base]) => {
    const amount = round2((base * rate) / 100);
    ht += round2(base);
    vat += amount;
    return { rate, base: round2(base), amount };
  });
  return { rows, ht: round2(ht), vat: round2(vat), ttc: round2(ht + vat) };
});

function addLine() {
  form.lines.push({ description: "", quantity: "1", unit: "C62", unit_price_ht: formatFixed(0, locale.value, 2), vat_rate: defaultRate.value });
}

function payload() {
  return {
    kind: doc.value!.kind,
    customer_id: form.customer_id,
    order_id: doc.value!.order_id,
    nature: form.nature,
    vat_on_debits: form.vat_on_debits,
    delivery_date: form.delivery_date || null,
    notes: form.notes || null,
    lines: form.lines
      .filter((l) => l.description.trim())
      .map((l) => ({
        description: l.description.trim(),
        quantity: String(parseNum(l.quantity) || 1),
        unit: l.unit || "C62",
        unit_price_ht: parseNum(l.unit_price_ht).toFixed(2),
        vat_rate: String(parseNum(l.vat_rate)),
      })),
  };
}

async function run(action: () => Promise<SalesDocument | void>, then?: (d: SalesDocument) => void) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  saved.value = false;
  try {
    const d = await action();
    if (d) {
      if (then) then(d);
      else fill(d);
    }
  } catch (err) {
    error.value = errorMessage(err, t);
  } finally {
    busy.value = false;
  }
}

const save = () => run(async () => {
  const d = await store.updateDocument(doc.value!.id, payload());
  saved.value = true;
  return d;
});

const issue = () =>
  run(async () => {
    await store.updateDocument(doc.value!.id, payload());
    if (doc.value!.kind !== "quote" && !confirm(t("doc.issueConfirm"))) return store.fetchDocument(doc.value!.id);
    return store.documentAction(doc.value!.id, "issue");
  });

const remove = () =>
  run(async () => {
    if (!confirm(t("doc.deleteConfirm"))) return;
    await store.deleteDocument(doc.value!.id);
    router.push("/documents");
  });

const creditNote = () => run(() => store.documentAction(doc.value!.id, "credit-note"), (d) => router.push(`/documents/${d.id}`));
const toInvoice = () => run(() => store.documentAction(doc.value!.id, "to-invoice"), (d) => router.push(`/documents/${d.id}`));
const setStatus = (s: string) => run(() => store.documentStatus(doc.value!.id, s));

// e-mail the document, or remind the customer of an unpaid invoice
const mail = ref<MailPurpose | null>(null);
const canRemind = computed(() => doc.value?.kind === "invoice" && Number(doc.value.balance_due) > 0);
const nextLevel = computed(() => {
  const levels = (doc.value?.events ?? []).filter((e) => e.kind === "reminder").map((e) => e.level ?? 1);
  return String(Math.min(3, (levels.length ? Math.max(...levels) : 0) + 1)) as MailPurpose;
});
function mailed(d: SalesDocument) {
  mail.value = null;
  fill(d);
}
const docTitle = computed(() => (doc.value?.is_deposit ? t("documents.deposit") : t(`documents.kinds.${doc.value?.kind}`)));

async function openPdf(download: boolean) {
  error.value = "";
  try {
    if (editable.value) await store.updateDocument(doc.value!.id, payload());
    const blob = await store.documentPdf(doc.value!.id, download);
    if (download) {
      saveBlob(blob, `${t(`documents.kinds.${doc.value!.kind}`).toLowerCase()}-${doc.value!.number ?? "brouillon"}.pdf`);
    } else {
      window.open(URL.createObjectURL(blob), "_blank");
    }
  } catch (err) {
    error.value = errorMessage(err, t);
  }
}

const fmtDate = (iso: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(locale.value === "fr" ? "fr-FR" : "en-GB") : "—");
const customerName = (c: Customer) => (c.is_business && c.company_name ? c.company_name : c.name);
const units = [
  { code: "C62", key: "doc.unit.piece" },
  { code: "HUR", key: "doc.unit.hour" },
  { code: "MTR", key: "doc.unit.metre" },
];
</script>

<template>
  <div v-if="doc" class="page max-w-4xl">
    <router-link to="/documents" class="back-link">&larr; {{ t("documents.title") }}</router-link>
    <div class="flex items-center gap-3 flex-wrap">
      <h1 class="page-title">{{ docTitle }} {{ doc.number ?? t("documents.draft") }}</h1>
      <span class="tag font-medium" :class="DOCUMENT_STATUS_TAG[doc.status]">{{ t(`documents.status.${doc.kind}.${doc.status}`) }}</span>
      <span v-if="doc.corrects_number" class="text-sm text-slate-600">{{ t("doc.corrects", { number: doc.corrects_number }) }}</span>
    </div>
    <p v-if="doc.frozen" class="mt-2 text-sm text-slate-600 max-w-prose">{{ t("doc.frozenHint") }}</p>

    <p v-if="error" role="alert" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="editable && doc.missing.length && doc.kind !== 'quote'" class="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
      <p class="font-medium">{{ t("doc.missingTitle") }}</p>
      <ul class="mt-1 list-disc list-inside">
        <li v-for="m in doc.missing" :key="m">{{ t(`doc.missing.${m}`) }}</li>
      </ul>
      <router-link v-if="doc.missing.some((m) => m.startsWith('seller'))" to="/settings" class="mt-1 inline-block underline underline-offset-2">{{ t("doc.goSettings") }}</router-link>
    </div>

    <section class="sheet p-5 mt-6">
      <div class="field-grid grid sm:grid-cols-3 gap-3">
        <div class="sm:col-span-2">
          <label class="field-label" for="doc-customer">{{ t("doc.customer") }}</label>
          <select id="doc-customer" v-model.number="form.customer_id" :disabled="!editable" class="input w-full">
            <option :value="null">{{ t("doc.pickCustomer") }}</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ customerName(c) }}{{ c.city ? ` · ${c.city}` : "" }}</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="doc-nature">{{ t("doc.nature") }}</label>
          <select id="doc-nature" v-model="form.nature" :disabled="!editable" class="input w-full">
            <option value="goods">{{ t("doc.natures.goods") }}</option>
            <option value="services">{{ t("doc.natures.services") }}</option>
            <option value="mixed">{{ t("doc.natures.mixed") }}</option>
          </select>
        </div>
        <div v-if="doc.kind !== 'quote'">
          <label class="field-label" for="doc-delivery">{{ t("doc.deliveryDate") }}</label>
          <input id="doc-delivery" v-model="form.delivery_date" type="date" :disabled="!editable" class="input w-full" />
        </div>
        <div v-if="doc.issue_date">
          <span class="field-label">{{ t("doc.issueDate") }}</span>
          <p class="h-9 flex items-center text-sm tabular-nums">{{ fmtDate(doc.issue_date) }}</p>
        </div>
        <div v-if="doc.due_date || doc.valid_until">
          <span class="field-label">{{ doc.kind === "quote" ? t("doc.validUntil") : t("doc.dueDate") }}</span>
          <p class="h-9 flex items-center text-sm tabular-nums">{{ fmtDate(doc.kind === "quote" ? doc.valid_until : doc.due_date) }}</p>
        </div>
      </div>
      <label v-if="!franchise && form.nature !== 'goods'" class="mt-3 flex items-center gap-2 text-sm text-slate-700">
        <input v-model="form.vat_on_debits" type="checkbox" :disabled="!editable" /> {{ t("doc.vatOnDebits") }}
      </label>
      <p v-if="!form.customer_id && editable" class="mt-2 text-xs text-slate-500">
        <router-link to="/customers" class="link-action text-xs">{{ t("doc.newCustomer") }}</router-link>
      </p>
    </section>

    <section class="sheet p-5 mt-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="sheet-title">{{ t("doc.lines") }}</h2>
        <button v-if="editable" class="link-action" @click="addLine">+ {{ t("doc.addLine") }}</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs font-medium text-slate-500">
              <th class="pb-1 pr-2 w-full">{{ t("doc.col.description") }}</th>
              <th class="pb-1 px-2 text-right">{{ t("doc.col.qty") }}</th>
              <th class="pb-1 px-2">{{ t("doc.col.unit") }}</th>
              <th class="pb-1 px-2 text-right">{{ franchise ? t("doc.col.price") : t("doc.col.priceHt") }}</th>
              <th v-if="!franchise" class="pb-1 px-2 text-right">{{ t("doc.col.vat") }}</th>
              <th class="pb-1 pl-2 text-right">{{ franchise ? t("doc.col.total") : t("doc.col.totalHt") }}</th>
              <th v-if="editable"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(l, i) in form.lines" :key="i" class="border-t border-slate-100 align-middle">
              <td class="py-1.5 pr-2 min-w-[14rem]">
                <input v-model="l.description" :disabled="!editable" :aria-label="t('doc.col.description')" class="input-sm w-full" />
              </td>
              <td class="py-1.5 px-2"><input v-model="l.quantity" :disabled="!editable" inputmode="decimal" :aria-label="t('doc.col.qty')" class="input-sm w-16 text-right tabular-nums" /></td>
              <td class="py-1.5 px-2">
                <select v-model="l.unit" :disabled="!editable" :aria-label="t('doc.col.unit')" class="input-sm">
                  <option v-for="u in units" :key="u.code" :value="u.code">{{ t(u.key) }}</option>
                </select>
              </td>
              <td class="py-1.5 px-2"><input v-model="l.unit_price_ht" :disabled="!editable" inputmode="decimal" :aria-label="t('doc.col.priceHt')" class="input-sm w-24 text-right tabular-nums" /></td>
              <td v-if="!franchise" class="py-1.5 px-2"><input v-model="l.vat_rate" :disabled="!editable" inputmode="decimal" :aria-label="t('doc.col.vat')" class="input-sm w-16 text-right tabular-nums" /></td>
              <td class="py-1.5 pl-2 text-right tabular-nums whitespace-nowrap">{{ money(lineTotal(l)) }}</td>
              <td v-if="editable" class="py-1.5 pl-2">
                <button class="p-1 rounded text-slate-500 hover:text-red-700 hover:bg-slate-100" :aria-label="t('common.delete')" @click="form.lines.splice(i, 1)"><EditorIcon name="close" :size="14" /></button>
              </td>
            </tr>
            <tr v-if="!form.lines.length">
              <td :colspan="franchise ? 5 : 6" class="py-4 text-center text-slate-500">{{ t("doc.noLines") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <dl class="mt-4 ml-auto max-w-xs space-y-1 text-sm">
        <template v-if="!franchise">
          <div class="flex justify-between"><dt class="text-slate-600">{{ t("doc.totalHt") }}</dt><dd class="tabular-nums">{{ money(totals.ht) }}</dd></div>
          <div v-for="r in totals.rows" :key="r.rate" class="flex justify-between">
            <dt class="text-slate-600">{{ t("doc.vatLine", { rate: r.rate }) }}</dt><dd class="tabular-nums">{{ money(r.amount) }}</dd>
          </div>
        </template>
        <div class="flex justify-between pt-1 border-t border-slate-200 font-semibold text-base">
          <dt>{{ franchise ? t("doc.total") : t("doc.totalTtc") }}</dt><dd class="tabular-nums">{{ money(totals.ttc) }}</dd>
        </div>
        <p v-if="franchise" class="text-xs text-slate-500 text-right">{{ t("doc.franchiseMention") }}</p>
        <template v-if="Number(doc.prepaid_amount) > 0">
          <div v-for="r in doc.prepaid_refs" :key="r.number" class="flex justify-between gap-3 text-slate-600">
            <dt>{{ t("doc.depositDeducted", { number: r.number }) }}</dt><dd class="tabular-nums whitespace-nowrap">− {{ money(Number(r.amount)) }}</dd>
          </div>
          <div class="flex justify-between pt-1 border-t border-slate-200 font-semibold">
            <dt>{{ t("doc.leftToPay") }}</dt><dd class="tabular-nums">{{ money(totals.ttc - Number(doc.prepaid_amount)) }}</dd>
          </div>
        </template>
      </dl>
    </section>

    <section class="sheet p-5 mt-4">
      <label class="field-label" for="doc-notes">{{ t("doc.notes") }}</label>
      <textarea id="doc-notes" v-model="form.notes" rows="2" :disabled="!editable" class="input w-full"></textarea>
    </section>

    <div class="mt-6 flex flex-wrap items-center gap-2">
      <template v-if="editable">
        <button class="btn btn-primary" :disabled="busy" @click="issue">{{ doc.kind === "quote" ? t("doc.issueQuote") : t("doc.issueInvoice") }}</button>
        <button class="btn btn-outline" :disabled="busy" @click="save">{{ t("common.save") }}</button>
        <button class="btn btn-outline" @click="openPdf(false)">{{ t("doc.preview") }}</button>
        <span v-if="saved" class="text-sm text-green-700" role="status">{{ t("settings.shop.saved") }}</span>
        <button class="link-danger ml-auto" @click="remove">{{ t("doc.deleteDraft") }}</button>
      </template>
      <template v-else>
        <button class="btn btn-primary" @click="openPdf(true)">{{ doc.kind === "quote" ? t("doc.downloadPdf") : t("doc.downloadFacturx") }}</button>
        <button class="btn btn-outline" @click="openPdf(false)">{{ t("doc.preview") }}</button>
        <template v-if="doc.kind === 'quote'">
          <button v-if="doc.status !== 'refused'" class="btn btn-outline" :disabled="busy" @click="toInvoice">{{ t("doc.toInvoice") }}</button>
          <button v-if="doc.status === 'issued'" class="btn btn-outline" :disabled="busy" @click="setStatus('refused')">{{ t("doc.markRefused") }}</button>
        </template>
        <template v-else>
          <button v-if="canRemind" class="btn btn-outline" :disabled="busy" @click="mail = nextLevel">{{ t("doc.remind") }}</button>
          <button v-if="doc.kind === 'invoice'" class="link-action ml-auto" :disabled="busy" @click="creditNote">{{ t("doc.creditNote") }}</button>
        </template>
        <button class="btn btn-outline" :disabled="busy" @click="mail = 'send'">{{ t("doc.sendByMail") }}</button>
      </template>
    </div>

    <div v-if="!editable" class="mt-6 grid gap-4 lg:grid-cols-2 items-start">
      <DocumentPayments v-if="doc.kind !== 'quote'" :doc="doc" @update="fill" />
      <DocumentHistory :events="doc.events" />
    </div>
    <DocumentMailDialog v-if="mail && doc" :doc="doc" :purpose="mail" @done="mailed" @close="mail = null" />
    <p v-if="!editable && doc.kind !== 'quote'" class="mt-3 text-xs text-slate-500 max-w-prose">{{ t("documents.einvoicingNote") }}</p>
  </div>
  <p v-else-if="error" class="page text-sm text-red-700">{{ error }}</p>
</template>
