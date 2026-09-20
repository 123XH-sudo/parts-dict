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
    <div v-else class="boxes">
      <button
        v-for="n in boxes"
        :key="n"
        type="button"
        :class="{ on: q.trim() === n + '号盒' }"
        @click="goBox(n)"
      >
        {{ n }}号盒
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { readJson, request } from "../api.js";

const route = useRoute();
const router = useRouter();
const q = ref(String(route.query.q || ""));
const results = ref([]);
const boxes = ref([]);
const searched = ref(false);
const loading = ref(false);
let timer = 0;

async function load() {
  const query = q.value.trim();
  loading.value = Boolean(query);
  const res = await request("GET", "/api/parts" + (query ? `?q=${encodeURIComponent(query)}` : ""));
  const data = await readJson(res);
  results.value = data.results || [];
  boxes.value = data.boxes || [];
  searched.value = Boolean(query);
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
  q.value = `${n}号盒`;
  router.push({ path: "/", query: { q: q.value } });
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
