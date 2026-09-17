# 料盒字典 Vue 单页界面

日期：2026-09-17  
状态：待你确认后写实现计划  
产品名：料盒字典  
仓库：`/home/skez/Downloads/parts-dict`  
前置：`docs/superpowers/specs/2026-09-16-parts-dict-design.md`（业务规则不变）

---

## 1. 要解决的问题

业务功能已经能用，页面是 Jinja 服务器渲染的白底表单，工位上对着焊接图不好扫。要换成 **Vue 3 单页应用**：简约、功能一眼能懂，查找和本板贴片仍是主路径。

业务规则不改：搜索、登记、同格冲突、修改记录、账号、盒数、BOM 匹配、打开清单按当前字典重配、备份导出。

---

## 2. 目标与非目标

### 2.1 成功标准

- 打开原来的地址（本机 `8787` 或以后的域名），看到的是新界面，不是旧 HTML 表单。
- 对着焊接图输入 `10K`，1 秒内看到 **几号盒第几格**。
- 登录、登记、改料、停用、本板贴片、历史、账号、备份，行为与现在一致。
- Docker 仍 **一个容器**，不另开 Node 进程给工位用。
- 组员不能打开账号管理；未登录只能看到登录页。

### 2.2 本期不做

- Element Plus、Naive UI 等组件库。
- 前后端两个网址、JWT、跨域 Token。
- 「记住我」、组员改自己密码（原业务设计有，本次界面重构不顺手加）。
- 从 BOM「登记」时自动勾极性（可仍预填简称）。
- 暗色主题、侧栏、仪表盘、图表。
- 把 SQLite 换成别的库。

---

## 3. 架构

```
浏览器  →  GET /           →  Vue（history 路由）
         →  /api/*         →  FastAPI JSON（Cookie Session + CSRF）
         →  静态资源       →  Vite 打包文件
```

- 前端目录：`web/`（Vite + Vue 3 + Vue Router）。无 Pinia 也可：登录用户放一个小 `session` 模块。
- 后端：现有 `app/`。Jinja 业务页删除；FastAPI 提供 `/api` 并托管 `web/dist`。
- 未匹配的 GET 路径（非 `/api`、非带点的静态文件）返回 `index.html`，由 Vue Router 处理。
- 开发：`web` 的 Vite 代理 `/api` 到 `127.0.0.1:8787`；生产：Nginx 或容器内只暴露 FastAPI。

Docker 多阶段：Node 构建 `web` → 拷到 Python 镜像的 `app/static/spa`（或 `web/dist` 由 FastAPI 指向该目录）。工位不跑 `npm`。

---

## 4. 页面与路由

| 路由 | 谁能进 | 内容 |
|---|---|---|
| `/login` | 未登录 | 标题「料盒字典」、用户名、密码、登录。已登录则去 `/` |
| `/` | 已登录 | 大搜索框；空查询显示盒按钮；有查询显示结果或「登记：词」 |
| `/parts/new` | 已登录 | 登记表；`?alias=` 预填简称和详细名 |
| `/parts/:id/edit` | 已登录 | 同一张表；底部「停用这条料」 |
| `/jobs` | 已登录 | 上传 BOM + 已上传的板列表 |
| `/jobs/:id` | 已登录 | 极性红条 / 按盒 / 未登记 / 不用拿 |
| `/history` | 已登录 | 时间、人、动作、对象、摘要 |
| `/users` | 管理员 | 盒数、用户、开组员、导出备份；组员进此路由由前端根据角色去首页，API 仍 403 |

顶栏（登录后）：登记、本板贴片、修改记录、账号（仅管理员）、显示名、退出。没有汉堡菜单。

---

## 5. 视觉

- 浅灰/白底、近黑字、系统字体栈（无网上下载字体）。
- 搜索框是页上最大的控件（约 20–22px 字）。
- 位置「3号盒第5格」加粗。
- 极性区浅红底 + 深红色标题「有极性，别贴反」。
- 盒号为小矩形按钮，选中时描边加粗，不是彩虹色。
- 主按钮一个深色填色；停用为文字按钮，不抢眼。
- 宽度：查找/本板约 960px 居中；表单约 560px。手机能滚动能点，不为手机单独做套布局。

---

## 6. API

一律 JSON。Cookie 带 Session。写操作带 CSRF：先 `GET /api/csrf`（未登录也可）拿到 `csrf_token`，之后请求头带 `X-CSRF-Token`。已登录时 `GET /api/me` 也会带回新 token。multipart 上传可同时放表单字段 `csrf_token`。

未登录访问业务 API：`401`，body `{ "detail": "未登录" }`。组员打管理员 API：`403`，`{ "detail": "只有管理员能管账号" }`。校验失败：`400`，`{ "detail": "中文原因" }`（同格冲突、减盒失败等）。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/csrf` | 未登录也可用，`{csrf_token}` |
| POST | `/api/login` | `{username, password}`，成功 204 |
| POST | `/api/logout` | 204 |
| GET | `/api/me` | `{username, display_name, role, box_count, csrf_token}` |
| GET | `/api/parts?q=` | `{results:[{id, aliases, name, box, slot, location, qty_kind, qty_count, qty_label}]}`；`q` 空则 `{results:[], boxes:[1..N]}` |
| POST | `/api/parts` | 登记，成功 `{id}` 201 |
| GET | `/api/parts/{id}` | 编辑回填 |
| PUT | `/api/parts/{id}` | 保存 |
| POST | `/api/parts/{id}/deactivate` | 停用 |
| GET | `/api/history` | `{rows:[...]}` |
| GET | `/api/jobs` | `{jobs:[{id,title,source_filename}]}` |
| POST | `/api/jobs` | multipart：`file` + `title`，成功 201 `{id}` |
| GET | `/api/jobs/{id}` | 打开时 **重配** 当前字典；返回 polar / box_groups / unreg / skip |
| GET | `/api/users` | 管理员 |
| POST | `/api/users` | 开组员 |
| POST | `/api/users/{id}/disable` | 停用账号 |
| POST | `/api/users/{id}/reset-password` | `{password}` |
| PUT | `/api/settings/box_count` | `{box_count}` |
| GET | `/api/backup.json` | 管理员下载 JSON，不含 `password_hash` |

数量档文案仍由后端给 `qty_label`，前端不复制一套「少量/大量」。

搜索、BOM 匹配、同格占用、减盒拦截，算法留在 Python（`search.py` / `bom.py`），Vue 只展示。

---

## 7. 前端模块

| 文件（拟定） | 职责 |
|---|---|
| `web/src/api.js` | fetch 封装：credentials、CSRF、401 跳登录 |
| `web/src/session.js` | 当前用户与 `box_count` |
| `web/src/App.vue` | 顶栏 + `router-view` |
| `web/src/pages/Login.vue` | 登录 |
| `web/src/pages/Home.vue` | 搜索与盒按钮 |
| `web/src/pages/PartForm.vue` | 登记/编辑 |
| `web/src/pages/Jobs.vue` / `Job.vue` | 本板贴片 |
| `web/src/pages/History.vue` | 修改记录 |
| `web/src/pages/Users.vue` | 账号 |
| `web/src/styles.css` | 唯一样式表 |

查找输入 300ms 防抖后请求 `GET /api/parts?q=`；盒按钮跳 `/?q=3号盒`（与现在语义相同）。

---

## 8. 错误处理

- 登录失败：登录页一句「用户名或密码不对」，不区分哪项错。
- 网络失败：当前页一句「没存上，请重试」，不假装成功。
- 表单 400：把 `detail` 显示在表单顶部，留在本页。
- CSRF 过期：再请求 `GET /api/csrf` 或 `GET /api/me` 后重提交一次；仍失败再提示过期。

---

## 9. 测试

现有 pytest 从解析 HTML 改为打 `/api`（登录仍用 Cookie）。行为断言保持：

- 未登录改数据 → 401
- 搜 `10K` / `10k 0603` / `3号盒`
- 改格子后历史有「旧 → 新」
- 停用后搜不到
- 组员 403 账号与备份
- 同格冲突
- 样例 BOM 69 行、极性名单、`10K` 不配 `10K1N`
- 先上传后登记，再 GET 该 job，位置已在「按盒拿料」
- 备份 JSON 无密码

不强制 Vue 单测。Docker 构建必须能 `npm run build` 再启动，打开 `/` 为 Vue 应用。

---

## 10. 迁移

- 删除 `app/templates/` 下业务 Jinja（login/home/part_form/history/users/jobs/job/forbidden）。
- 保留 Python 模型、审计、BOM 解析。
- README：开发需 Node 20+ 做 `web` 构建；工位只访问已构建的服务。

---

## 11. 决策摘要

| 问题 | 决定 |
|---|---|
| 前端 | Vue 3 + Vite + Vue Router，自写 CSS |
| 后端 | FastAPI JSON `/api`，Cookie Session |
| 部署 | 单容器，FastAPI 托管 `dist` |
| 组件库 | 不用 |
| 业务规则 | 与 2026-09-16 设计一致 |
