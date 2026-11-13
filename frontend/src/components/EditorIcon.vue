<script setup lang="ts">
/** The editor's one icon set: 20 px, 1.5 px stroke, drawn in currentColor so it
 *  follows the slate chrome (never a layer colour, see DESIGN.md). */
import { computed } from "vue";

export type EditorIconName =
  | "select" | "node" | "pen" | "rect" | "ellipse" | "line" | "polygon" | "arc" | "dimension" | "measure" | "pan"
  | "library" | "holes" | "notch" | "swing" | "scroll" | "text" | "undo" | "redo" | "fit" | "magnet" | "eye" | "eye-off" | "lock" | "unlock"
  | "close" | "chevron-down" | "chevron-up" | "warning" | "swap"
  | "flip-h" | "flip-v" | "mirror-h" | "mirror-v" | "rotate" | "duplicate";

const props = defineProps<{ name: EditorIconName; size?: number }>();

const PATHS: Record<EditorIconName, string> = {
  select: "M5 3l11 7.5-5 1.2L8.6 17z",
  node: "M10 3l7 7-7 7-7-7z M10 8.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 1 0 0-3",
  pen: "M4 16l1.5-5L13 3.5l3.5 3.5L9 14.5zM4 16l4-1M11 5.5l3.5 3.5",
  rect: "M3.5 5.5h13v9h-13z",
  ellipse: "M10 4.5c4 0 7 2.5 7 5.5s-3 5.5-7 5.5-7-2.5-7-5.5 3-5.5 7-5.5z",
  line: "M4 16L16 4M4 16a.75.75 0 1 0 0 .01M16 4a.75.75 0 1 0 0 .01",
  polygon: "M10 3l6.5 3.75v6.5L10 17l-6.5-3.75v-6.5z",
  arc: "M3.5 14a6.5 6.5 0 0 1 13 0M3.5 14h0M16.5 14h0M10 7.5h0",
  dimension: "M3 5v10M17 5v10M3 10h14M6 7.5L3 10l3 2.5M14 7.5l3 2.5-3 2.5",
  measure: "M2.5 13.5L13.5 2.5l4 4-11 11zM6 10l1.5 1.5M8.5 7.5L10 9M11 5l1.5 1.5",
  pan: "M7 10V4.5a1.25 1.25 0 0 1 2.5 0V9.5M9.5 9V3.5a1.25 1.25 0 0 1 2.5 0V9.5M12 9.5V5a1.25 1.25 0 0 1 2.5 0v6.5c0 3-2 5.5-5 5.5h-.5c-2 0-3.2-1-4.3-2.6L2.8 11.4a1.2 1.2 0 0 1 1.9-1.5L7 12",
  library: "M3.5 3.5h5v5h-5zM11.5 3.5h5v5h-5zM3.5 11.5h5v5h-5zM11.5 11.5h5v5h-5z",
  holes: "M5.5 7a2 2 0 1 0 0 .01M14.5 7a2 2 0 1 0 0 .01M5.5 14a2 2 0 1 0 0 .01M14.5 14a2 2 0 1 0 0 .01M3.5 5a2 2 0 1 0 4 0 2 2 0 1 0-4 0",
  // a spine with three V notches
  notch: "M2.5 7h3l1.5 2.5 1.5-2.5h1l1.5 2.5 1.5-2.5h1l1.5 2.5 1.5-2.5h1.5M2.5 7v6.5h15V7",
  // a blade swinging about its pivot
  scroll: "M10 10a1.5 1.5 0 1 1 1.5 1.5A3 3 0 0 1 8.5 8.5a4.5 4.5 0 0 1 4.5-4.5 6 6 0 0 1 6 6M2.5 16.5h7",
  swing: "M5 14.5h11l1.5-2.5H5zM5 14.5a1.2 1.2 0 1 0 0 .01M5 12.5L13 5.5l2 .5-1 1.8-8.5 5.2M9 16.8a7 7 0 0 0 1.5-11.6",
  text: "M4.5 5V3.5h11V5M10 3.5v13M7.5 16.5h5",
  undo: "M7.5 4.5L4 8l3.5 3.5M4 8h7.5a4.5 4.5 0 0 1 0 9H8",
  redo: "M12.5 4.5L16 8l-3.5 3.5M16 8H8.5a4.5 4.5 0 0 0 0 9H12",
  fit: "M3.5 7.5v-4h4M12.5 3.5h4v4M16.5 12.5v4h-4M7.5 16.5h-4v-4M7 7h6v6H7z",
  magnet: "M5 3.5v6.5a5 5 0 0 0 10 0V3.5h-3.5V10a1.5 1.5 0 0 1-3 0V3.5zM5 7h3.5M11.5 7H15",
  eye: "M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10zM10 7.75a2.25 2.25 0 1 0 0 4.5 2.25 2.25 0 1 0 0-4.5",
  "eye-off": "M3 3l14 14M8.2 5a8.6 8.6 0 0 1 1.8-.2c5 0 8 5.2 8 5.2a14 14 0 0 1-2.3 2.9M12.6 14.9a8 8 0 0 1-2.6.4c-5 0-8-5.3-8-5.3a14.5 14.5 0 0 1 3.2-3.6",
  lock: "M5 9h10v8H5zM7 9V6.5a3 3 0 0 1 6 0V9",
  unlock: "M5 9h10v8H5zM7 9V6.5a3 3 0 0 1 5.8-1",
  close: "M5 5l10 10M15 5L5 15",
  "chevron-down": "M5.5 8l4.5 4.5L14.5 8",
  "chevron-up": "M5.5 12l4.5-4.5 4.5 4.5",
  swap: "M4 7h11l-3-3M16 13H5l3 3",
  "flip-h": "M10 2.5v15M7.5 5L3 15h4.5zM12.5 5L17 15h-4.5z",
  "flip-v": "M2.5 10h15M5 7.5L15 3v4.5zM5 12.5L15 17v-4.5z",
  "mirror-h": "M10 2.5v15M7.5 5L3 15h4.5zM12.5 5L17 15h-4.5zM14 3.5h3v3",
  "mirror-v": "M2.5 10h15M5 7.5L15 3v4.5zM5 12.5L15 17v-4.5zM16.5 14v3h-3",
  rotate: "M15.5 7.5A6 6 0 1 0 16 12M16 3.5v4h-4",
  duplicate: "M7 7h9.5v9.5H7zM4 13V4h9",
  warning: "M10 3l7.5 13.5h-15zM10 8v4M10 14.5h0",
};

const d = computed(() => PATHS[props.name]);
</script>

<template>
  <svg
    :width="size ?? 20"
    :height="size ?? 20"
    viewBox="0 0 20 20"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path :d="d" />
  </svg>
</template>
