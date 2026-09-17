<template>
  <div class="page">
    <h1>本板贴片</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <h2>上传嘉立创 BOM</h2>
    <form @submit.prevent="upload">
      <label for="title">短名称</label>
      <input id="title" v-model="title" placeholder="无刷驱动 PCB1">
      <label for="file">xlsx 或 csv</label>
      <input id="file" type="file" accept=".xlsx,.csv" @change="onFile">
      <button type="submit">生成清单</button>
    </form>
    <template v-if="jobs.length">
      <h2>已上传的板</h2>
      <table>
        <thead><tr><th>名称</th><th>文件</th></tr></thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td><router-link :to="`/jobs/${job.id}`">{{ job.title }}</router-link></td>
            <td>{{ job.source_filename }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { loadCsrf, readJson, request } from "../api.js";

const router = useRouter();
const title = ref("");
const file = ref(null);
const jobs = ref([]);
const error = ref("");

async function load() {
  const res = await request("GET", "/api/jobs");
  const data = await readJson(res);
  jobs.value = data.jobs || [];
}

function onFile(event) {
  file.value = event.target.files[0] || null;
}

async function upload() {
  error.value = "";
  if (!file.value) {
    error.value = "请用嘉立创导出的 BOM";
    return;
  }
  try {
    await loadCsrf();
    const form = new FormData();
    form.append("title", title.value);
    form.append("file", file.value);
    const res = await request("POST", "/api/jobs", { form });
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    router.push(`/jobs/${data.id}`);
  } catch {
    error.value = "没存上，请重试";
  }
}

onMounted(load);
</script>
