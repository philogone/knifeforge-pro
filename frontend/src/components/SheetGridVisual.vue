<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  sheetLength: number;
  sheetWidth: number;
  blankLength: number;
  blankWidth: number;
  cols: number;
  rows: number;
  rotated: boolean;
}>();

const WIDTH = 400;
const scale = computed(() => WIDTH / props.sheetLength);
const height = computed(() => props.sheetWidth * scale.value);

const cellW = computed(() => (props.rotated ? props.blankWidth : props.blankLength) * scale.value);
const cellH = computed(() => (props.rotated ? props.blankLength : props.blankWidth) * scale.value);

const cells = computed(() => {
  const out: { x: number; y: number }[] = [];
  for (let r = 0; r < props.rows; r++) {
    for (let c = 0; c < props.cols; c++) {
      out.push({ x: c * cellW.value, y: r * cellH.value });
    }
  }
  return out;
});
</script>

<template>
  <svg :width="WIDTH" :height="height" class="rounded overflow-hidden border border-slate-300">
    <rect x="0" y="0" :width="WIDTH" :height="height" fill="#f1f5f9" />
    <rect
      v-for="(cell, i) in cells"
      :key="i"
      :x="cell.x + 1"
      :y="cell.y + 1"
      :width="Math.max(cellW - 2, 0)"
      :height="Math.max(cellH - 2, 0)"
      fill="#6366f1"
      fill-opacity="0.85"
      stroke="white"
    />
  </svg>
</template>
