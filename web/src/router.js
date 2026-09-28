import { createRouter, createWebHistory } from "vue-router";
import { refreshSession, session } from "./session.js";
import Box from "./pages/Box.vue";
import Home from "./pages/Home.vue";
import History from "./pages/History.vue";
import Job from "./pages/Job.vue";
import Jobs from "./pages/Jobs.vue";
import Login from "./pages/Login.vue";
import Register from "./pages/Register.vue";
import PartForm from "./pages/PartForm.vue";
import Users from "./pages/Users.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login, meta: { public: true } },
    { path: "/register", component: Register, meta: { public: true } },
    { path: "/", component: Home },
    { path: "/boxes/:n", component: Box },
    { path: "/parts/new", component: PartForm },
    { path: "/parts/:id/edit", component: PartForm },
    { path: "/jobs", component: Jobs },
    { path: "/jobs/:id", component: Job },
    { path: "/history", component: History },
    { path: "/users", component: Users, meta: { admin: true } },
  ],
});

router.beforeEach(async (to) => {
  if (!session.user) {
    await refreshSession();
  }
  if (to.meta.public) {
    if (session.user && (to.path === "/login" || to.path === "/register")) return "/";
    return true;
  }
  if (!session.user) return "/login";
  if (to.meta.admin && session.user.role !== "admin") return "/";
  return true;
});

export default router;
