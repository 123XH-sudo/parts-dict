<template>
  <div class="page">
    <h1>账号</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <p><a href="/api/backup.json">导出备份 JSON</a>（元件、用户不含密码、修改记录、本板清单）</p>

    <h2>盒数</h2>
    <form @submit.prevent="saveBoxes">
      <label for="box_count">当前盒数（1～99）</label>
      <input id="box_count" v-model.number="boxCount" type="number" min="1" max="99">
      <button type="submit">保存盒数</button>
    </form>

    <h2>用户</h2>
    <table>
      <thead>
        <tr><th>用户名</th><th>显示名</th><th>角色</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.username }}</td>
          <td>{{ user.display_name }}</td>
          <td>{{ user.role === "admin" ? "管理员" : "组员" }}</td>
          <td>
            <span v-if="user.active">启用</span>
            <span v-else class="off">已停用</span>
          </td>
          <td>
            <button
              v-if="user.active && user.id !== currentUserId"
              type="button"
              class="quiet"
              @click="disableUser(user.id)"
            >
              停用
            </button>
            <form v-if="user.active" class="inline" @submit.prevent="resetPassword(user.id)">
              <input v-model="resets[user.id]" type="password" placeholder="新密码" required>
              <button type="submit">重置密码</button>
            </form>
          </td>
        </tr>
      </tbody>
    </table>

    <h2>开新账号</h2>
    <form @submit.prevent="createUser">
      <label for="username">用户名（字母数字下划线）</label>
      <input id="username" v-model="form.username" required>
      <label for="display_name">显示名</label>
      <input id="display_name" v-model="form.display_name" required>
      <label for="password">初始密码</label>
      <input id="password" v-model="form.password" type="password" required>
      <button type="submit">创建组员</button>
    </form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { readJson, request } from "../api.js";
import { refreshSession } from "../session.js";

const users = ref([]);
const boxCount = ref(12);
const currentUserId = ref(0);
const error = ref("");
const resets = reactive({});
const form = reactive({ username: "", display_name: "", password: "" });

async function load() {
  const res = await request("GET", "/api/users");
  const data = await readJson(res);
  if (!res.ok) {
    error.value = data?.detail || "只有管理员能管账号";
    return;
  }
  users.value = data.users || [];
  boxCount.value = data.box_count;
  currentUserId.value = data.current_user_id;
}

async function saveBoxes() {
  error.value = "";
  try {
    const res = await request("PUT", "/api/settings/box_count", { json: { box_count: boxCount.value } });
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    await refreshSession();
    await load();
  } catch {
    error.value = "没存上，请重试";
  }
}

async function createUser() {
  error.value = "";
  try {
    const res = await request("POST", "/api/users", { json: { ...form } });
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    form.username = "";
    form.display_name = "";
    form.password = "";
    await load();
  } catch {
    error.value = "没存上，请重试";
  }
}

async function disableUser(id) {
  error.value = "";
  try {
    const res = await request("POST", `/api/users/${id}/disable`);
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    await load();
  } catch {
    error.value = "没存上，请重试";
  }
}

async function resetPassword(id) {
  error.value = "";
  try {
    const res = await request("POST", `/api/users/${id}/reset-password`, {
      json: { password: resets[id] || "" },
    });
    const data = await readJson(res);
    if (!res.ok) {
      error.value = data?.detail || "没存上，请重试";
      return;
    }
    resets[id] = "";
    await load();
  } catch {
    error.value = "没存上，请重试";
  }
}

onMounted(load);
</script>
