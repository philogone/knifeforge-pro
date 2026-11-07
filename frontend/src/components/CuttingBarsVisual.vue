<script setup lang="ts">
import { computed } from "vue";

interface Piece {
  length: number;
  label: string;
}
interface Bar {
  pieces: Piece[];
  waste: number;
}

const props = defineProps<{
  stockLength: number;
  kerf: number;
  bars: Bar[];
}>();

const PALETTE = ["#6b7a2c", "#0ea5e9", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316"];

function colorFor(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

const WIDTH = 600;
const scale = computed(() => WIDTH / props.stockLength);

function segments(bar: Bar) {
  let x = 0;
  const out: { x: number; w: number; kerfX: number; kerfW: number; label: string; color: string }[] = [];
  for (const piece of bar.pieces) {
    const w = piece.length * scale.value;
    const kerfW = props.kerf * scale.value;
    out.push({ x, w, kerfX: x + w, kerfW, label: piece.label, color: colorFor(piece.label) });
    x += w + kerfW;
  }
  return out;
}
</script>

<template>
  <div class="space-y-3">
    <div v-for="(bar, i) in bars" :key="i" class="flex items-center gap-3">
      <span class="text-xs text-slate-500 w-14 shrink-0">#{{ i + 1 }}</span>
      <svg :width="WIDTH" height="28" class="rounded overflow-hidden border border-slate-300 shrink-0">
        <rect x="0" y="0" :width="WIDTH" height="28" fill="#f1f5f9" />
        <template v-for="(seg, j) in segments(bar)" :key="j">
          <rect :x="seg.x" y="0" :width="seg.w" height="28" :fill="seg.color">
            <title>{{ seg.label }}</title>
          </rect>
          <rect :x="seg.kerfX" y="0" :width="seg.kerfW" height="28" fill="#334155" />
        </template>
      </svg>
      <span class="text-xs text-slate-500 shrink-0">{{ bar.pieces.length }} pcs, {{ Math.round(bar.waste) }}mm waste</span>
    </div>
  </div>
</template>
