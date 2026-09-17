import { createRouter, createWebHistory } from "vue-router";
import { refreshSession, session } from "./session.js";
import Home from "./pages/Home.vue";
import Login from "./pages/Login.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login, meta: { public: true } },
    { path: "/", component: Home },
  ],
});

router.beforeEach(async (to) => {
  if (!session.user) {
    await refreshSession();
  }
  if (to.meta.public) {
    if (session.user && to.path === "/login") return "/";
    return true;
  }
  if (!session.user) return "/login";
  return true;
});

export default router;
