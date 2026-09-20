import { reactive } from "vue";
import { setCsrf } from "./api.js";

export const session = reactive({ user: null });

let pending = null;

export async function refreshSession() {
  if (pending) return pending;
  pending = (async () => {
    const res = await fetch("/api/me", { credentials: "include" });
    if (!res.ok) {
      session.user = null;
      return null;
    }
    session.user = await res.json();
    setCsrf(session.user.csrf_token);
    return session.user;
  })().finally(() => {
    pending = null;
  });
  return pending;
}
