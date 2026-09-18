<template>
  <div class="login-wrap">
    <div class="login">
    <h1>料盒字典</h1>
    <p class="hint">登录后才能查料和改库存。</p>
    <form @submit.prevent="submit">
      <label for="username">用户名</label>
      <input id="username" v-model="username" autocomplete="username" required>
      <label for="password">密码</label>
      <input id="password" v-model="password" type="password" autocomplete="current-password" required>
      <button type="submit">登录</button>
    </form>
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
const password = ref("");
const error = ref("");

async function submit() {
  error.value = "";
  try {
    await loadCsrf();
    const res = await request("POST", "/api/login", {
      json: { username: username.value, password: password.value },
    });
    if (!res.ok) {
      const body = await readJson(res);
      error.value = body?.detail || "用户名或密码不对";
      return;
    }
    await refreshSession();
    router.push("/");
  } catch {
    error.value = "没存上，请重试";
  }
}
</script>
