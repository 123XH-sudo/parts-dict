<template>
  <div class="page box-page">
    <div class="box-head">
      <p class="crumb"><router-link to="/">返回查找</router-link></p>
      <div class="box-title-row">
        <h1>{{ boxN }}号盒</h1>
        <div class="layout-edit">
          <label>
            列
            <input v-model.number="cols" type="number" min="1" max="24" @input="scheduleLayout">
          </label>
          <label>
            行
            <input v-model.number="rows" type="number" min="1" max="24" @input="scheduleLayout">
          </label>
        </div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div
      v-if="slots"
      class="slot-grid"
      :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }"
    >
      <button
        v-for="(part, index) in slots"
        :key="index"
        type="button"
        class="slot-cell"
        :class="{ filled: part, 'has-polar': part && part.polarized }"
        @click="openSlot(index + 1, part)"
      >
        <span class="slot-num">{{ index + 1 }}</span>
        <span v-if="part" class="slot-name">{{ part.aliases }}</span>
      </button>
    </div>
    <p v-else class="empty panel">加载中…</p>

    <div v-if="overflow.length" class="panel overflow">
      <h2>格子外的料</h2>
      <table>
        <thead>
          <tr><th>简称</th><th>格号</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="part in overflow" :key="part.id">
            <td>{{ part.aliases }}</td>
            <td>第{{ part.slot }}格</td>
            <td><router-link :to="`/parts/${part.id}/edit`">改</router-link></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { readJson, request } from "../api.js";

const route = useRoute();
const router = useRouter();
const boxN = computed(() => Number(route.params.n));
const cols = ref(8);
const rows = ref(6);
const slots = ref(null);
const overflow = ref([]);
const error = ref("");
let timer = 0;

async function load() {
  error.value = "";
  const res = await request("GET", `/api/boxes/${boxN.value}`);
  const data = await readJson(res);
  if (!res.ok) {
    error.value = data?.detail || "没有这个盒。";
    slots.value = [];
    overflow.value = [];
    return;
  }
  cols.value = data.cols;
  rows.value = data.rows;
  slots.value = data.slots || [];
  overflow.value = data.overflow || [];
}

function scheduleLayout() {
  clearTimeout(timer);
  timer = setTimeout(saveLayout, 400);
}

async function saveLayout() {
  error.value = "";
  const res = await request("PUT", `/api/boxes/${boxN.value}/layout`, {
    json: { cols: cols.value, rows: rows.value },
  });
  const data = await readJson(res);
  if (!res.ok) {
    error.value = data?.detail || "行列没存上。";
    return;
  }
  await load();
}

function openSlot(slot, part) {
  if (part) {
    router.push(`/parts/${part.id}/edit`);
    return;
  }
  router.push({ path: "/parts/new", query: { box: String(boxN.value), slot: String(slot) } });
}

watch(
  () => route.params.n,
  () => {
    slots.value = null;
    load();
  },
);

onMounted(load);
</script>
