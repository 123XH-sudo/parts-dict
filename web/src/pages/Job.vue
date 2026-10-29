<template>
  <div class="page">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="page">
      <p class="crumb"><router-link to="/jobs">本板贴片</router-link></p>
      <h1>{{ page.job.title }}</h1>
      <section class="polar">
        <h2>有极性，别贴反</h2>
        <div v-if="page.polar.length" class="table-wrap">
          <table class="job-table polar-table">
            <thead><tr><th>位号</th><th>规格</th><th>封装</th><th>耐压</th><th>位置</th><th>提醒</th></tr></thead>
            <tbody>
              <tr v-for="(row, i) in page.polar" :key="'p' + i">
                <td class="designators"><Designators :text="row.line.designators" /></td>
                <td>{{ row.line.name }}</td>
                <td>{{ row.line.footprint }}</td>
                <td class="voltage" :title="row.bom_voltage || row.part_voltage ? 'BOM 电压 → 库存耐压' : ''">
                  <template v-if="row.bom_voltage || row.part_voltage">
                    {{ row.bom_voltage || "—" }} → {{ row.part_voltage || "未标" }}
                  </template>
                </td>
                <td class="loc">{{ row.location || "未登记" }}</td>
                <td>{{ row.line.warning }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else>这一板没有需要极性提醒的料。</p>
      </section>

      <div class="panel">
      <h2>按盒拿料</h2>
      <template v-if="page.box_groups.length">
        <div v-for="group in page.box_groups" :key="group[0]">
          <h3>{{ group[0] }}号盒</h3>
          <div class="table-wrap">
            <table class="job-table box-table">
              <thead><tr><th>位号</th><th>规格</th><th>封装</th><th>耐压</th><th>位置</th><th>数量档</th></tr></thead>
              <tbody>
                <tr v-for="(row, i) in group[1]" :key="'b' + group[0] + i">
                  <td class="designators"><Designators :text="row.line.designators" /></td>
                  <td>{{ row.line.name }}</td>
                  <td>{{ row.line.footprint }}</td>
                  <td class="voltage" :title="row.bom_voltage || row.part_voltage ? 'BOM 电压 → 库存耐压' : ''">
                    <template v-if="row.bom_voltage || row.part_voltage">
                      {{ row.bom_voltage || "—" }} → {{ row.part_voltage || "未标" }}
                    </template>
                  </td>
                  <td class="loc">{{ row.location }}</td>
                  <td>{{ row.qty }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
      <p v-else class="empty">还没有匹配到料盒里的料。</p>
      </div>

      <div class="panel">
      <h2>未登记</h2>
      <div v-if="page.unreg.length" class="table-wrap">
        <table class="job-table unreg-table">
          <thead><tr><th>位号</th><th>规格</th><th>封装</th><th></th></tr></thead>
          <tbody>
            <tr v-for="(line, i) in page.unreg" :key="'u' + i">
              <td class="designators"><Designators :text="line.designators" /></td>
              <td>{{ line.name }}</td>
              <td>{{ line.footprint }}</td>
              <td>
                <router-link :to="{ path: '/parts/new', query: { alias: line.name } }">登记</router-link>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty">都已登记。</p>
      </div>

      <div class="panel">
      <h2>不用从料盒拿</h2>
      <details>
        <summary>测试点、铜条等（{{ page.skip.length }}）</summary>
        <div v-if="page.skip.length" class="table-wrap">
          <table class="job-table skip-table">
            <thead><tr><th>位号</th><th>规格</th><th>封装</th></tr></thead>
            <tbody>
              <tr v-for="(line, i) in page.skip" :key="'s' + i">
                <td class="designators"><Designators :text="line.designators" /></td>
                <td>{{ line.name }}</td>
                <td>{{ line.footprint }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { readJson, request } from "../api.js";
import Designators from "../components/Designators.vue";

const route = useRoute();
const page = ref(null);
const error = ref("");

async function load() {
  error.value = "";
  const res = await request("GET", `/api/jobs/${route.params.id}`);
  const data = await readJson(res);
  if (!res.ok) {
    error.value = data?.detail || "没有这块板。";
    page.value = null;
    return;
  }
  page.value = data;
}

watch(() => route.params.id, load);
onMounted(load);
</script>
