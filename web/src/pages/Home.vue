<template>
  <div class="page">
    <form class="search" @submit.prevent>
      <input
        v-model="q"
        type="search"
        placeholder="10K、0603、3号盒"
        autofocus
        @input="schedule"
      >
    </form>
    <div v-if="searched && results.length" class="panel">
    <table>
      <thead>
        <tr><th>简称</th><th>详细名称</th><th>位置</th><th>数量</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="part in results" :key="part.id">
          <td>{{ part.aliases }}</td>
          <td>{{ part.name }}</td>
          <td class="loc">{{ part.location }}</td>
          <td>{{ part.qty_label }}</td>
          <td><router-link :to="`/parts/${part.id}/edit`">改</router-link></td>
        </tr>
      </tbody>
    </table>
    </div>
    <p v-else-if="loading" class="empty panel">查找中…</p>
    <p v-else-if="searched" class="empty panel">
      没有「{{ q.trim() }}」。翻到后可以
      <router-link class="link" :to="{ path: '/parts/new', query: { alias: q.trim() } }">登记：{{ q.trim() }}</router-link>
    </p>
    <div v-else class="box-cards">
      <button
        v-for="card in cards"
        :key="card.n"
        type="button"
        class="box-card"
        @click="goBox(card.n)"
      >
        <span class="box-card-name">{{ card.n }}号盒</span>
        <span class="box-card-meta">{{ cardLabel(card) }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { readJson, request } from "../api.js";
import { session } from "../session.js";

const route = useRoute();
const router = useRouter();
const q = ref(String(route.query.q || ""));
const results = ref([]);
const summaries = ref([]);
const searched = ref(false);
const loading = ref(false);
let timer = 0;

const cards = computed(() => {
  const count = session.user?.box_count || summaries.value.length || 12;
  const byN = Object.fromEntries(summaries.value.map((row) => [row.n, row]));
  return Array.from({ length: count }, (_, i) => {
    const n = i + 1;
    return byN[n] || { n, cols: 8, rows: 6, used: null, total: 48 };
  });
});

function cardLabel(card) {
  if (card.used == null) return `${card.total} 格`;
  return `${card.used}/${card.total}`;
}

async function loadBoxes() {
  const res = await request("GET", "/api/boxes");
  const data = await readJson(res);
  if (res.ok) {
    summaries.value = data.boxes || [];
  }
}

async function load() {
  const query = q.value.trim();
  loading.value = Boolean(query);
  if (!query) {
    searched.value = false;
    results.value = [];
    loading.value = false;
    await loadBoxes();
    return;
  }
  const res = await request("GET", `/api/parts?q=${encodeURIComponent(query)}`);
  const data = await readJson(res);
  results.value = data.results || [];
  searched.value = true;
  loading.value = false;
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(() => {
    const query = q.value.trim();
    const current = String(route.query.q || "");
    if (current !== query) {
      router.replace({ path: "/", query: query ? { q: query } : {} });
    } else {
      load();
    }
  }, 300);
}

function goBox(n) {
  router.push(`/boxes/${n}`);
}

watch(
  () => route.query.q,
  (value) => {
    q.value = String(value || "");
    load();
  },
);

onMounted(load);
</script>
