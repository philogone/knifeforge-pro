<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { developedLength, forgingStock, sectionArea, type Point, type Reference, type Section } from "@/editor/developedLength";
import { formatLengthWithUnit, fromDisplay, toDisplay, type LengthUnit } from "@/editor/units";
import { useI18n } from "@/i18n";

/**
 * Developed length of the selected line (bar to cut to forge or bend it), and the bar length
 * holding a forged part's volume. Everything is computed here, from the drawing.
 */
const props = defineProps<{
  line: { points: Point[]; closed: boolean; area: number } | null;
  unit: LengthUnit;
  defaultThickness: number;
}>();
const emit = defineEmits<{ (e: "close"): void }>();
const { t, num } = useI18n();

const tab = ref<"bend" | "forge">(props.line?.closed && props.line.area > 0 ? "forge" : "bend");
const D = (mm: number) => Math.round(toDisplay(mm, props.unit) * 10000) / 10000;
const L = (v: number) => fromDisplay(Number(v) || 0, props.unit);
const fmt = (mm: number) => formatLengthWithUnit(mm, props.unit);
const u = computed(() => props.unit);

const f = reactive({
  kind: "square" as Section["kind"],
  d: D(12), a: D(12), w: D(30), th: D(6), onEdge: false,
  reference: "centre" as Reference,
  k: 0.5,
  extra: D(0),
  loss: 0,
  density: 7.85,
  partThickness: D(props.defaultThickness),
});

const section = computed<Section>(() =>
  f.kind === "round" ? { kind: "round", d: L(f.d) } : f.kind === "square" ? { kind: "square", a: L(f.a) } : { kind: "flat", w: L(f.w), t: L(f.th), onEdge: f.onEdge },
);

const bend = computed(() =>
  props.line ? developedLength(props.line.points, props.line.closed, section.value, f.reference, Number(f.k) || 0.5, L(f.extra), Number(f.loss) || 0, Number(f.density) || 7.85) : null,
);

const forge = computed(() => {
  if (!props.line?.closed || !(props.line.area > 0)) return null;
  const volume = props.line.area * L(f.partThickness);
  const length = forgingStock(volume, section.value, Number(f.loss) || 0) + L(f.extra);
  return { volume, length, weightG: (sectionArea(section.value) * length * (Number(f.density) || 7.85)) / 1000 };
});

const g = (grams: number) => (grams >= 1000 ? `${num(grams / 1000, 2)} kg` : `${num(grams, 0)} g`);
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" role="dialog" aria-modal="true" aria-labelledby="dl-title" @keydown.esc="emit('close')">
    <div class="bg-paper rounded-xl shadow-xl w-full max-w-xl max-h-[92vh] overflow-y-auto p-5 text-sm space-y-4">
      <div class="flex items-start justify-between gap-3">
        <h2 id="dl-title" class="sheet-title">{{ t("dl.title") }}</h2>
        <button class="btn btn-outline btn-sm" @click="emit('close')">{{ t("common.close") }}</button>
      </div>
      <p v-if="!line" class="text-amber-800">{{ t("dl.pick") }}</p>
      <template v-else>
        <div class="flex gap-1" role="tablist">
          <button v-for="k in (['bend', 'forge'] as const)" :key="k" type="button" role="tab" :aria-selected="tab === k"
                  class="px-3 py-1.5 rounded-lg border" :class="tab === k ? 'bg-slate-800 text-paper border-slate-800' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
                  :disabled="k === 'forge' && !(line.closed && line.area > 0)" @click="tab = k">{{ t(`dl.tabs.${k}`) }}</button>
        </div>
        <p class="text-slate-600">{{ tab === "bend" ? t("dl.bendLead") : t("dl.forgeLead") }}</p>

        <fieldset class="grid gap-3 sm:grid-cols-3">
          <legend class="field-label mb-1">{{ t("dl.section") }}</legend>
          <label class="block">
            <span class="field-label">{{ t("dl.profile") }}</span>
            <select v-model="f.kind" class="input w-full">
              <option value="round">{{ t("dl.kinds.round") }}</option>
              <option value="square">{{ t("dl.kinds.square") }}</option>
              <option value="flat">{{ t("dl.kinds.flat") }}</option>
            </select>
          </label>
          <label v-if="f.kind === 'round'" class="block"><span class="field-label">{{ t("dl.diameter", { u }) }}</span><input v-model.number="f.d" type="number" min="0.1" step="any" class="input w-full" /></label>
          <label v-if="f.kind === 'square'" class="block"><span class="field-label">{{ t("dl.side", { u }) }}</span><input v-model.number="f.a" type="number" min="0.1" step="any" class="input w-full" /></label>
          <template v-if="f.kind === 'flat'">
            <label class="block"><span class="field-label">{{ t("dl.width", { u }) }}</span><input v-model.number="f.w" type="number" min="0.1" step="any" class="input w-full" /></label>
            <label class="block"><span class="field-label">{{ t("dl.thickness", { u }) }}</span><input v-model.number="f.th" type="number" min="0.1" step="any" class="input w-full" /></label>
            <label v-if="tab === 'bend'" class="sm:col-span-3 flex items-center gap-2"><input v-model="f.onEdge" type="checkbox" /> {{ t("dl.onEdge") }}</label>
          </template>
        </fieldset>

        <div v-if="tab === 'bend'" class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="field-label">{{ t("dl.reference") }}</span>
            <select v-model="f.reference" class="input w-full">
              <option value="centre">{{ t("dl.refs.centre") }}</option>
              <option value="inside">{{ t("dl.refs.inside") }}</option>
              <option value="outside">{{ t("dl.refs.outside") }}</option>
            </select>
          </label>
          <label class="block">
            <span class="field-label">{{ t("dl.k") }}</span>
            <input v-model.number="f.k" type="number" min="0.2" max="0.5" step="0.01" class="input w-full" />
            <span class="block mt-1 text-xs text-slate-500">{{ t("dl.kHint") }}</span>
          </label>
        </div>
        <div v-else class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="field-label">{{ t("dl.partThickness", { u }) }}</span>
            <input v-model.number="f.partThickness" type="number" min="0.1" step="any" class="input w-full" />
          </label>
        </div>

        <div class="grid gap-3 sm:grid-cols-3">
          <label class="block"><span class="field-label">{{ t("dl.extra", { u }) }}</span><input v-model.number="f.extra" type="number" min="0" step="any" class="input w-full" /></label>
          <label class="block"><span class="field-label">{{ t("dl.loss") }}</span><input v-model.number="f.loss" type="number" min="0" max="50" step="0.5" class="input w-full" /></label>
          <label class="block"><span class="field-label">{{ t("dl.density") }}</span><input v-model.number="f.density" type="number" min="0.1" step="0.01" class="input w-full" /></label>
        </div>

        <dl v-if="tab === 'bend' && bend" class="rounded-lg bg-slate-50 p-3 grid grid-cols-2 gap-y-1">
          <dt class="text-slate-500">{{ t("dl.drawn") }}</dt><dd class="text-right tabular-nums">{{ fmt(bend.drawn) }} · {{ num(bend.turningDeg, 0) }}°</dd>
          <dt class="text-slate-500">{{ t("dl.neutral") }}</dt><dd class="text-right tabular-nums">{{ fmt(bend.neutral) }}</dd>
          <dt class="text-slate-500">{{ t("dl.allowances") }}</dt><dd class="text-right tabular-nums">+ {{ fmt(bend.allowances) }}</dd>
          <dt class="font-semibold">{{ t("dl.cut") }}</dt><dd class="text-right tabular-nums font-semibold">{{ fmt(bend.cut) }}</dd>
          <dt class="text-slate-500">{{ t("dl.weight") }}</dt><dd class="text-right tabular-nums">{{ g(bend.weightG) }}</dd>
        </dl>
        <dl v-if="tab === 'forge' && forge" class="rounded-lg bg-slate-50 p-3 grid grid-cols-2 gap-y-1">
          <dt class="text-slate-500">{{ t("dl.volume") }}</dt><dd class="text-right tabular-nums">{{ num(forge.volume / 1000, 2) }} cm³</dd>
          <dt class="font-semibold">{{ t("dl.stock") }}</dt><dd class="text-right tabular-nums font-semibold">{{ fmt(forge.length) }}</dd>
          <dt class="text-slate-500">{{ t("dl.weight") }}</dt><dd class="text-right tabular-nums">{{ g(forge.weightG) }}</dd>
        </dl>
        <p class="text-xs text-slate-500">{{ tab === "bend" ? t("dl.bendLimits") : t("dl.forgeLimits") }}</p>
      </template>
    </div>
  </div>
</template>
