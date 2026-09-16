# 料盒字典

贴片时查找元件在几号盒、第几格。全组共用，需登录。

当前可测：**登录 / 退出**。搜索、登记、BOM 贴片清单尚未做。

## 本机运行

```bash
cd parts-dict
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# 改 .env 里的 SECRET_KEY 和 ADMIN_PASSWORD
mkdir -p data
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
```

浏览器打开 http://127.0.0.1:8787

- 默认用户名见 `.env` 的 `ADMIN_USERNAME`（示例是 `admin`）
- 密码是 `ADMIN_PASSWORD`
- 错误密码应提示「用户名或密码不对」
- 登录成功后看到首页和你的用户名，点「退出」回到登录页
- 未登录访问首页会跳到登录

## 测试

```bash
.venv/bin/pytest -v
```
