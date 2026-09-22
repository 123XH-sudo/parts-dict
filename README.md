# 料盒字典

办公室实验室共用的贴片物料字典。对着嘉立创辅助焊接图，按规格查几号盒、第几格；全组登录，改动留记录。

界面是 Vue 单页，由同一个 FastAPI 进程提供 `/api` 和页面。工位只用浏览器，不用装 Node。

## 工位怎么打开

系统跑在办公室服务器上，**用服务器的地址打开**，不要用 `127.0.0.1`（那是机器自己，别人电脑打不开）。

- 未做域名时：`http://<服务器IP>:8787`
- 已反代 HTTPS 时：用配好的域名

登录后即可查找、进盒看格子、登记物料。管理员可开账号、改盒数、导出备份。

## 服务器部署

需要 Docker。目录默认 `/opt/parts-dict`。

```bash
git clone git@github.com:123XH-sudo/parts-dict.git /opt/parts-dict
cd /opt/parts-dict
cp .env.example .env
# 改 .env 里的 SECRET_KEY 和 ADMIN_PASSWORD
mkdir -p data
docker compose up -d --build
```

容器把 `8787` 映射出来。工位浏览器打开 `http://<服务器IP>:8787`。

`./data` 挂到容器里，升级程序不会冲掉库存。定期复制 `data/parts.db`，或用管理员页的「导出备份 JSON」（不含密码哈希）。

环境变量写在 `.env`，不要提交到 Git：

| 变量 | 作用 |
|---|---|
| `SECRET_KEY` | Session 签名密钥，必须改成足够长的随机串 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 仅库里还没有用户时创建第一个管理员 |
| `TZ` | 页面时间，默认 `Asia/Shanghai` |
| `DATABASE_URL` | 默认 `sqlite:///./data/parts.db` |

## 服务器更新

脚本会先备份 `data/` 和 `.env`，再拉最新代码并 `docker compose up -d --build`。库存文件不会被覆盖。

第一次（目录里还没有 git 也可以）：

```bash
curl -fsSL https://raw.githubusercontent.com/123XH-sudo/parts-dict/main/scripts/update.sh | bash
```

以后每次：

```bash
/opt/parts-dict/scripts/update.sh
```

备份在 `/opt/parts-dict-backups/`，默认留最近 10 份。目录或仓库地址不同时：

```bash
APP_DIR=/opt/parts-dict REPO=git@github.com:123XH-sudo/parts-dict.git /opt/parts-dict/scripts/update.sh
```

## 反代 / HTTPS（可选）

容器只提供 `8787`。若要用域名和证书，在服务器 Nginx 里反代到本机这个端口，工位打开的是域名，不是回源地址。

```nginx
server {
    listen 443 ssl;
    server_name 你的域名;
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

上面 `proxy_pass` 里的回环地址只给 Nginx 在服务器本机回源用，工位不要打开它。

## 本机开发

需要 Python 3.12 和 Node 20+（只用来构建前端）。监听 `0.0.0.0`，同一局域网可用本机 IP 打开。

```bash
cd parts-dict
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web && npm install && SPA_OUT=../app/static/spa npm run build && cd ..
cp .env.example .env
# 改 .env 里的 SECRET_KEY 和 ADMIN_PASSWORD
mkdir -p data
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8787
```

浏览器打开 `http://<本机IP>:8787`。只在这台电脑上看也可以用 `http://localhost:8787`。

开发前端时可另开终端：`cd web && npm run dev`（Vite 把 `/api` 代理到 8787）。改完后仍用上面的 `SPA_OUT=... npm run build`，再用 8787 打开完整界面。

```bash
.venv/bin/pytest -v
```
