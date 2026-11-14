<script setup lang="ts">
/** The KnifeForge mark: a full-tang drop point on the olive tile (same drawing as the favicon). */
withDefaults(defineProps<{ size?: number }>(), { size: 28 });
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="7" class="fill-accent-600" />
    <g transform="translate(16.2 16.2) rotate(-35) scale(.84) translate(-18.5 -3.4)">
      <path d="M.8.4 14.4 0V4.6C12.6 4.6 11.6 4.1 10 4.4 7.5 4.9 5 5.5 2.8 5.3 1 5.1 0 4.3 0 2.6 0 1.4.3.5.8.4Z" class="fill-accent-100" />
      <circle cx="4.6" cy="2.5" r=".6" class="fill-accent-600" />
      <circle cx="10.4" cy="2.2" r=".6" class="fill-accent-600" />
      <path d="M15.4 0H27C30.6 0 34 1.4 37 3 34 5.4 30.4 6.2 26.4 6.2H18.2C17.4 6.2 17.3 7 16.4 7 15.8 7 15.4 6.6 15.4 6Z" fill="#fff" />
      <path d="M19.6 6.2C20.4 4.6 20.6 3.5 22 3.5H29C32 3.5 34.4 3.2 37 3 34 5.4 30.4 6.2 26.4 6.2Z" class="fill-accent-200" />
    </g>
  </svg>
</template>
