<template>
  <details v-if="items.length > 10">
    <summary>{{ items.slice(0, 6).join(", ") }} …（共 {{ items.length }} 个）</summary>
    <span class="designator-full">{{ items.join(", ") }}</span>
  </details>
  <template v-else>{{ items.join(", ") }}</template>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  text: { type: String, default: "" },
});

const items = computed(() =>
  String(props.text || "")
    .split(/[,，;；\s]+/)
    .filter(Boolean)
);
</script>
