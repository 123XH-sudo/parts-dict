# 料盒字典

办公室实验室共用的贴片物料字典。对着嘉立创辅助焊接图，按规格查几号盒、第几格。

**同事直接打开：** [http://47.93.206.216:8787/](http://47.93.206.216:8787/)

界面是 Vue 单页，由同一个 FastAPI 进程提供 `/api` 和页面。工位只用浏览器，不用装 Node。

## 简介

贴片工位上，电阻、电容、二极管、电感一部分散在桌面、袋子和抽屉里，要用时只能翻桌子。另一部分已经放进料盒，但格子上的手写标签字迹模糊、掉字，地方又小，封装、精度、极性经常写不全。一格里有时堆着几样看着像、又不敢肯定是不是同一型号的料。找一颗料往往要从第一格挨个翻，或者问还记得位置的人。人不在，焊接就停。位置记在个人脑子或小纸片上，换工位、换人又得重新问一遍。

对着嘉立创焊接图贴板时，困难更具体：BOM 上的规格要对应到盒子里的哪一格；二极管、MOS、电解电容贴反会坏，单靠模糊标签看不出来。同一种料如果被两个人各记一格，拿料时不知道该去哪。

料盒字典把已经归位的料记成全组共用的一份目录。工位打开浏览器就能查，不用在每台电脑上装软件。

### 主要功能

- **查找。** 输入规格、封装或盒号（如 `10K`、`0603`、`3号盒`），直接看到几号盒第几格和大概数量。对着焊接图搜，然后去对应格子拿。
- **登记与料盒。** 每颗料记下详细名称、工位简称、盒号、格号、数量档和有没有极性。首页按盒展示，点进盒子是和实物对应的格子图；点空格即可登记并带上盒号格号。同一种料只能占一个格子，再登会提示已有位置。高精度和普通料、普通电阻和热敏可以分开记。
- **本板贴片。** 上传嘉立创 BOM 后，按当前字典配到格子，清单按盒分组，方便顺着盒子拿。有极性的料单独列出，并写明别贴反时看哪里。`10kΩ`、`10KR` 和带封装的简称可以对上同一颗料。
- **账号。** 登录后才能查和改库存。没有账号的人可以自己注册，注册后是组员。管理员可以开账号、停用账号、改盒数、导出不含密码的备份。
- **修改记录。** 谁在什么时间改了哪颗料、从哪一格到哪一格，留在记录里，方便核对，也避免整理成果只留在某个人电脑上。

## 工位怎么打开

浏览器打开 [http://47.93.206.216:8787/](http://47.93.206.216:8787/) ，登录后即可查找、进盒看格子、登记物料。管理员可开账号、改盒数、导出备份。

这是已经部署好的办公室服务器，工位电脑和手机都能用这个地址。

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

容器把 `8787` 映射出来。工位打开 [http://47.93.206.216:8787/](http://47.93.206.216:8787/) 。

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
