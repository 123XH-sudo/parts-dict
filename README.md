# 料盒字典

贴片时对着嘉立创辅助焊接图，按规格查找元件在几号盒、第几格。全组共用，需登录。

界面是 Vue 单页，由同一个 FastAPI 进程提供 `/api` 和页面。工位不用装 Node。

## 本机运行

需要 Python 3.12 和 Node 20+（只用来构建前端）。

```bash
cd parts-dict
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web && npm install && SPA_OUT=../app/static/spa npm run build && cd ..
cp .env.example .env
# 改 .env 里的 SECRET_KEY 和 ADMIN_PASSWORD
mkdir -p data
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
```

浏览器打开 http://127.0.0.1:8787

开发前端时可另开终端：`cd web && npm run dev`（Vite 把 `/api` 代理到 8787）。改完后仍用上面的 `SPA_OUT=... npm run build`，再用 8787 打开完整界面。

环境变量（写在 `.env`，不要提交到 Git）：

| 变量 | 作用 |
|---|---|
| `SECRET_KEY` | Session 签名密钥，必须改成足够长的随机串 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 仅库里还没有用户时创建第一个管理员 |
| `TZ` | 页面时间，默认 `Asia/Shanghai` |
| `DATABASE_URL` | 默认 `sqlite:///./data/parts.db` |

数据文件在 `data/parts.db`。备份这个文件，或用管理员账号页的「导出备份 JSON」（不含密码哈希）。

## Docker

```bash
cp .env.example .env
# 改 SECRET_KEY 和 ADMIN_PASSWORD
mkdir -p data
docker compose up -d --build
```

Compose 把本机 `./data` 挂到容器 `/app/data`，升级镜像时库存不会丢。定期复制 `data/parts.db`。

## 反代 / HTTPS

容器或 uvicorn 只监听内网 `8787`。用已有 Nginx 证书对外，例如：

```nginx
server {
    listen 443 ssl;
    server_name parts.example.com;
    # ssl_certificate / ssl_certificate_key 用你现有的

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

工位电脑和手机用同一域名打开即可。

## 测试

```bash
.venv/bin/pytest -v
```
