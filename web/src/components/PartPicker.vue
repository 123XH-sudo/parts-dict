<template>
  <div class="picker-backdrop" @click.self="$emit('close')">
    <div class="picker panel">
      <div class="picker-head">
        <h2>重新指定位置</h2>
        <button type="button" class="link-btn" @click="$emit('close')">关闭</button>
      </div>
      <p class="hint">
        <strong>{{ designators }}</strong> · BOM：{{ name }}{{ footprint ? ` / ${footprint}` : "" }}
        <template v-if="currentLocation"> · 当前：{{ currentLocation }}</template>
      </p>
      <form class="search" @submit.prevent="searchNow($event)">
        <input
          v-model="q"
          type="search"
          placeholder="搜规格、封装或盒号"
          @input="schedule"
        >
        <button type="submit" class="search-btn">搜索</button>
      </form>
      <p v-if="loading" class="empty">查找中…</p>
      <ul v-else class="picker-list">
        <li v-for="part in results" :key="part.id">
          <button type="button" class="picker-item" @click="$emit('select', part)">
            <span class="picker-name">{{ part.name }}</span>
            <span class="picker-meta">
              {{ part.aliases }} · {{ part.location }} · {{ part.qty_label }}
            </span>
          </button>
        </li>
        <li v-if="!results.length" class="empty">没有匹配的料，换个关键词试试。</li>
      </ul>
      <div v-if="currentId" class="picker-foot">
        <button type="button" class="text-btn" @click="$emit('clear')">恢复自动匹配</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { readJson, request } from "../api.js";

const props = defineProps({
  designators: { type: String, default: "" },
  name: { type: String, default: "" },
  footprint: { type: String, default: "" },
  currentLocation: { type: String, default: "" },
  currentId: { type: Number, default: null },
});

defineEmits(["close", "select", "clear"]);

const q = ref(props.name || "");
const results = ref([]);
const loading = ref(false);
let timer = 0;
let seq = 0;

async function searchNow(event) {
  clearTimeout(timer);
  const typed = event?.target?.querySelector?.('input[type="search"]')?.value;
  if (typeof typed === "string") q.value = typed;
  const query = q.value.trim();
  const mine = ++seq;
  if (!query) {
    results.value = [];
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    const res = await request("GET", `/api/parts?q=${encodeURIComponent(query)}`);
    const data = await readJson(res);
    if (mine !== seq) return;
    results.value = data?.results || [];
  } finally {
    if (mine === seq) loading.value = false;
  }
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(searchNow, 250);
}

onMounted(searchNow);
</script>
