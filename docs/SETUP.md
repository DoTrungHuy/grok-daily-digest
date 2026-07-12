# 设置说明（唯一主文档）

## 架构

```text
twitter-cli + X Cookie  →  x_raw/
DeepSeek API            →  digests/
build_site              →  docs/*.html
GitHub Actions 08:17 北京 → 自动 commit digests/docs
GitHub Actions deploy-pages → 主动发布 GitHub Pages
```

也就是“双线更新”：

```text
第一条线：生成后的 digests/ 和 docs/ commit 回仓库
第二条线：把 docs/ 上传为 Pages artifact，并由 deploy-pages 发布网站
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
pip install -r requirements.txt
$env:DEEPSEEK_API_KEY="..."
$env:TWITTER_AUTH_TOKEN="..."
$env:TWITTER_CT0="..."
python scripts/run_daily.py
```

## Pages

Settings → Pages → Source → **GitHub Actions**

不要再使用旧方式：

```text
Deploy from a branch → main → /docs
```

改成 GitHub Actions 后，网站由 `.github/workflows/daily.yml` 中的 `deploy-pages` job 发布。

访问：`https://<user>.github.io/X-daily-digest/`

## 合并前验证分支

在 PR 分支上建议分两步验收：

1. 先运行 `Run workflow`，选择 `feat/actions-pages-dual-update`，保持 `deploy_pages=false`。  
   这会验证抓取、生成、commit 是否成功，不会触发 `github-pages` 部署环境。
2. 如果要在合并前也验证线上网站部署，需要进入 `Settings → Environments → github-pages`，允许 `feat/actions-pages-dual-update` 部署，然后再次运行 workflow，并把 `deploy_pages=true`。

原因：`github-pages` 是一个部署环境，GitHub 会检查这个 environment 的分支保护规则；如果 feature 分支没有被允许，部署 job 会在启动前被拦截。

合并到 `main` 后，定时任务会按 UTC `17 0 * * *`，即北京/新加坡 **08:17** 自动跑，并在 `main` 上 commit + deploy。

## 改「想看的内容」

编辑 `config/accounts.yaml`（账号 + 搜索词），提交即可。

## 代理（A1）

先直连跑 3～7 天 Actions；常失败再设 `HTTPS_PROXY`。
