<template>
  <div class="login-wrap">
    <div class="login">
      <h1>注册</h1>
      <p class="hint">注册后就是组员，可以查料、改库存、上传 BOM。</p>
      <form @submit.prevent="submit">
        <label for="username">用户名（字母、数字或下划线）</label>
        <input id="username" v-model="username" autocomplete="username" required>
        <label for="display_name">显示名（可空）</label>
        <input id="display_name" v-model="displayName" autocomplete="nickname">
        <label for="password">密码（至少 8 位）</label>
        <input id="password" v-model="password" type="password" autocomplete="new-password" required>
        <label for="password2">再输入一次密码</label>
        <input id="password2" v-model="password2" type="password" autocomplete="new-password" required>
        <button type="submit">注册并进入</button>
      </form>
      <p class="switch"><router-link to="/login">已有账号？登录</router-link></p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { loadCsrf, readJson, request } from "../api.js";
import { refreshSession } from "../session.js";

const router = useRouter();
const username = ref("");
const displayName = ref("");
const password = ref("");
const password2 = ref("");
const error = ref("");

async function submit() {
  error.value = "";
  if (password.value !== password2.value) {
    error.value = "两次密码不一致。";
    return;
  }
  try {
    await loadCsrf();
    const res = await request("POST", "/api/register", {
      json: {
        username: username.value,
        display_name: displayName.value,
        password: password.value,
      },
    });
    if (!res.ok) {
      const body = await readJson(res);
      error.value = body?.detail || "没注册上，请重试";
      return;
    }
    await refreshSession();
    router.push("/");
  } catch {
    error.value = "没注册上，请重试";
  }
}
</script>
