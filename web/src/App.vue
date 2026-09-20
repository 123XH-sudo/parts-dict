<template>
  <div class="app">
    <header v-if="session.user && route.path !== '/login'" class="topbar">
      <div class="top">
        <router-link to="/" class="brand">料盒字典</router-link>
        <nav>
          <router-link to="/parts/new">登记</router-link>
          <router-link to="/jobs">本板贴片</router-link>
          <router-link to="/history">修改记录</router-link>
          <router-link v-if="session.user.role === 'admin'" to="/users">账号</router-link>
          <span class="who">{{ session.user.display_name || session.user.username }}</span>
          <button type="button" class="text-btn" @click="logout">退出</button>
        </nav>
      </div>
    </header>
    <router-view />
  </div>
</template>

<script setup>
import { useRoute, useRouter } from "vue-router";
import { request } from "./api.js";
import { session } from "./session.js";

const route = useRoute();
const router = useRouter();

async function logout() {
  try {
    await request("POST", "/api/logout");
  } catch {
    /* still leave */
  }
  session.user = null;
  router.push("/login");
}

</script>
