<template>
  <div class="page narrow">
    <p><router-link to="/">返回查找</router-link></p>
    <h1>{{ heading }}</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <form @submit.prevent="save">
      <label for="name">详细名称</label>
      <input id="name" v-model="form.name" required>
      <label for="aliases">通用简称（逗号分隔）</label>
      <input id="aliases" v-model="form.aliases" required>
      <label>盒号</label>
      <div class="boxes">
        <label v-for="n in boxList" :key="n">
          <input v-model.number="form.box" type="radio" :value="n"> {{ n }}
        </label>
      </div>
      <label for="slot">格号</label>
      <input id="slot" v-model.number="form.slot" type="number" min="1" required>
      <label>数量</label>
      <label><input v-model="form.qty_kind" type="radio" value="empty"> 没有</label>
      <label><input v-model="form.qty_kind" type="radio" value="few"> 少量</label>
      <label><input v-model="form.qty_kind" type="radio" value="many"> 大量</label>
      <label><input v-model="form.qty_kind" type="radio" value="exact"> 具体数字</label>
      <input v-model.number="form.qty_count" type="number" min="0" placeholder="选具体数字时填写">
      <label><input v-model="form.polarized" type="checkbox"> 有极性（贴反会坏）</label>
      <label for="note">备注</label>
      <input id="note" v-model="form.note">
      <button type="submit">保存</button>
    </form>
    <p v-if="partId">
      <button type="button" class="text-btn" @click="deactivate">停用这条料</button>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { readJson, request } from "../api.js";
import { session } from "../session.js";

const route = useRoute();
const router = useRouter();
const error = ref("");
const partId = computed(() => route.params.id);
const heading = computed(() => (partId.value ? "改元件" : "登记元件"));
const boxList = computed(() => {
  const n = session.user?.box_count || 12;
  return Array.from({ length: n }, (_, i) => i + 1);
});
const form = reactive({
  name: "",
  aliases: "",
  box: 1,
  slot: 1,
  qty_kind: "few",
  qty_count: null,
  polarized: false,
  note: "",
});

onMounted(async () => {
  if (partId.value) {
    const res = await request("GET", `/api/parts/${partId.value}`);
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没有这条料。";
      return;
    }
    Object.assign(form, {
      name: data.name,
      aliases: data.aliases,
      box: data.box,
      slot: data.slot,
      qty_kind: data.qty_kind,
      qty_count: data.qty_count,
      polarized: data.polarized,
      note: data.note || "",
    });
    return;
  }
  const alias = String(route.query.alias || "");
  if (alias) {
    form.name = alias;
    form.aliases = alias;
  }
});

function payload() {
  return {
    name: form.name,
    aliases: form.aliases,
    box: form.box,
    slot: form.slot,
    qty_kind: form.qty_kind,
    qty_count: form.qty_kind === "exact" ? form.qty_count : null,
    polarized: form.polarized,
    note: form.note,
  };
}

async function save() {
  error.value = "";
  try {
    const res = partId.value
      ? await request("PUT", `/api/parts/${partId.value}`, { json: payload() })
      : await request("POST", "/api/parts", { json: payload() });
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    router.push("/");
  } catch {
    error.value = "没存上，请重试";
  }
}

async function deactivate() {
  if (!partId.value) return;
  error.value = "";
  try {
    const res = await request("POST", `/api/parts/${partId.value}/deactivate`);
    if (!res.ok) {
      const data = await readJson(res);
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    router.push("/");
  } catch {
    error.value = "没存上，请重试";
  }
}
</script>
