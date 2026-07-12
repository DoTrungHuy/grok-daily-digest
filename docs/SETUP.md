# 设置说明（唯一主文档）

## 架构

```text
twitter-cli + X Cookie  →  x_raw/
DeepSeek API            →  digests/
build_site              →  docs/*.html
GitHub Actions 08:00 北京 → 自动 commit
GitHub Pages /docs      → 网站
```

## Secrets（仓库 Settings → Actions）

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `TWITTER_AUTH_TOKEN` | x.com Cookie `auth_token` |
| `TWITTER_CT0` | x.com Cookie `ct0` |
| `HTTPS_PROXY` | 可选；**A1 先不配**，直连失败再加 |

### 导出 Cookie

1. 浏览器登录 https://x.com  
2. Cookie-Editor / DevTools 复制 `auth_token`、`ct0`  
3. 粘贴到 Secrets（勿提交到 Git、勿发聊天）

## 本机试跑

```powershell
cd 仓库目录
pip install pyyaml twitter-cli
$env:DEEPSEEK_API_KEY="..."
$env:TWITTER_AUTH_TOKEN="..."
$env:TWITTER_CT0="..."
python scripts/run_daily.py
```

## Pages

Settings → Pages → Deploy from branch → `main` → **/docs**

访问：`https://<user>.github.io/grok-daily-digest/`

## 改「想看的内容」

编辑 `config/accounts.yaml`（账号 + 搜索词），提交即可。

## 代理（A1）

先直连跑 3～7 天 Actions；常失败再设 `HTTPS_PROXY`。

## 定时

`.github/workflows/daily.yml`：UTC `0 0 * * *` = 北京 **08:00**
