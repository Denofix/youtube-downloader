<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 });
const paths: Record<string, string> = {
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  convert: "M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4",
  tasks: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  settings: "M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6M9 15v6",
  language:
    "M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0M2 12h20M12 2c-5 5-5 15 0 20 5-5 5-15 0-20",
  link: "m9 15 6-6M8 17l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2-1 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  upload: "M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5",
  check: "m5 12 4 4L19 6",
  clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  file: "M14 2H4v20h16V8l-6-6v6h6M8 13h8M8 17h5",
  x: "m6 6 12 12M6 18 18 6",
};
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.file" />
  </svg>
</template>
