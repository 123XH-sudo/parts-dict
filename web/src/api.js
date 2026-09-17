let csrf = "";

export function setCsrf(token) {
  if (token) csrf = token;
}

export async function request(method, url, { json, form } = {}) {
  const headers = {};
  if (csrf) headers["X-CSRF-Token"] = csrf;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form !== undefined) {
    body = form;
  }
  const res = await fetch(url, { method, headers, body, credentials: "include" });
  if (res.status === 401 && url !== "/api/login" && url !== "/api/me") {
    if (window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw new Error("未登录");
  }
  return res;
}

export async function loadCsrf() {
  const res = await request("GET", "/api/csrf");
  const data = await res.json();
  csrf = data.csrf_token;
  return csrf;
}

export async function readJson(res) {
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}
