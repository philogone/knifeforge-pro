<script setup lang="ts">
import { computed } from "vue";

import type { NestingSheet } from "@/types";

const props = defineProps<{ sheet: NestingSheet; length: number; width: number; margin: number }>();

const PALETTE = ["#c7d2fe", "#bae6fd", "#bbf7d0", "#fde68a", "#fbcfe8", "#fed7aa", "#a5f3fc", "#ddd6fe"];

const shapes = computed(() =>
  props.sheet.placements.map((p) => {
    const d = p.outline
      .map((ring) => "M" + ring.map(([x, y]) => `${x.toFixed(3)} ${y.toFixed(3)}`).join("L") + "Z")
      .join("");
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const ring of p.outline) for (const [x, y] of ring) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
    return { d, color: PALETTE[p.design_id % PALETTE.length], cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, w: maxX - minX, h: maxY - minY, p };
  }),
);
const fontSize = computed(() => Math.max(2, Math.min(props.width, props.length) / 14));
</script>

<template>
  <svg :viewBox="`-2 -2 ${length + 4} ${width + 4}`" class="w-full bg-paper rounded border border-slate-200" preserveAspectRatio="xMidYMid meet">
    <rect x="0" y="0" :width="length" :height="width" fill="#f8fafc" stroke="#64748b" stroke-width="0.4" vector-effect="non-scaling-stroke" />
    <rect
      v-if="margin > 0"
      :x="margin" :y="margin" :width="length - 2 * margin" :height="width - 2 * margin"
      fill="none" stroke="#94a3b8" stroke-dasharray="3 3" stroke-width="0.3" vector-effect="non-scaling-stroke"
    />
    <g v-for="(s, i) in shapes" :key="i">
      <path :d="s.d" :fill="s.color" fill-rule="evenodd" stroke="#0f172a" stroke-width="1" vector-effect="non-scaling-stroke">
        <title>{{ s.p.part_name }} — {{ s.p.design_name }}{{ s.p.customer_name ? " — " + s.p.customer_name : "" }} ({{ s.p.rotation_deg }}°)</title>
      </path>
      <text
        v-if="s.w > fontSize * 3 && s.h > fontSize * 1.5"
        :x="s.cx" :y="s.cy" :font-size="fontSize" text-anchor="middle" dominant-baseline="middle" fill="#334155" pointer-events="none"
      >{{ s.p.part_name }}</text>
    </g>
  </svg>
</template>
