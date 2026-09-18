<template>
  <div class="page">
    <h1>修改记录</h1>
    <div v-if="rows.length" class="panel">
    <table>
      <thead>
        <tr><th>时间</th><th>人</th><th>动作</th><th>对象</th><th>摘要</th></tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="i">
          <td>{{ row.at }}</td>
          <td>{{ row.who }}</td>
          <td>{{ row.action }}</td>
          <td>{{ row.target }}</td>
          <td>{{ row.summary }}</td>
        </tr>
      </tbody>
    </table>
    </div>
    <p v-else class="empty panel">还没有修改记录。</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { readJson, request } from "../api.js";

const rows = ref([]);

onMounted(async () => {
  const res = await request("GET", "/api/history");
  const data = await readJson(res);
  rows.value = data.rows || [];
});
</script>
