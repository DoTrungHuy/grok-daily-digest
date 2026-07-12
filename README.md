# X Daily Digest

[![Site](https://img.shields.io/badge/🌐_Online-GitHub_Pages-0ea5e9?style=for-the-badge)](https://dotrunghuy.github.io/X-daily-digest/)
[![Repo](https://img.shields.io/badge/📦_Source-GitHub-181717?style=for-the-badge&logo=github)](https://github.com/DoTrungHuy/X-daily-digest)
[![Schedule](https://img.shields.io/badge/⏰_Daily-08:17_Beijing-8b5cf6?style=for-the-badge)](https://github.com/DoTrungHuy/X-daily-digest/actions)
[![Cost](https://img.shields.io/badge/💰_X_API-Not_used-22c55e?style=for-the-badge)](https://dotrunghuy.github.io/X-daily-digest/)

**免费读 X（Cookie / twitter-cli）→ DeepSeek 完整精读 → GitHub Actions 双线更新 → GitHub Pages 日更。**

---

## 🔗 部署地址（线上站点）

| 用途 | 链接 |
|------|------|
| 🌐 **网站首页** | **https://dotrunghuy.github.io/X-daily-digest/** |
| 📦 源码仓库 | https://github.com/DoTrungHuy/X-daily-digest |
| ⚙️ Actions 运行记录 | https://github.com/DoTrungHuy/X-daily-digest/actions |
| 🔐 Secrets 配置页 | https://github.com/DoTrungHuy/X-daily-digest/settings/secrets/actions |
| 📄 Pages 设置 | https://github.com/DoTrungHuy/X-daily-digest/settings/pages |

站点由 **GitHub Actions 主动部署 GitHub Pages**：workflow 先生成 `digests/` 和 `docs/`，再把结果 commit 回仓库，同时把 `docs/` 作为 Pages artifact 发布。

---

## ✨ 它做什么

```text
X Cookie 抓取  →  DeepSeek 策展  →  digests/*.md  →  docs 静态站  →  Actions 部署 Pages
   twitter-cli         完整精读           每日归档          仓库留档          网站日更
```

- **免费读 X**：用浏览器 Cookie + `twitter-cli`，不用付费 X API  
- **完整正文**：DeepSeek 输出 HOOK / META / ITEM / CLOSE 结构化精读  
- **双线更新**：GitHub Actions 每天北京时间约 **08:17** 跑一遍，既 commit 仓库，又主动部署 Pages  
- **阅读站**：暗黑适合阅读式 UI（适配 digest 卡片结构）

---

## 🚀 怎么用（推荐：只配一次）

### 1️⃣ 准备 Secrets

打开：  
https://github.com/DoTrungHuy/X-daily-digest/settings/secrets/actions

新增（或更新）以下 **Repository secrets**：

| Secret | 说明 | 怎么拿 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | [platform.deepseek.com](https://platform.deepseek.com) |
| `TWITTER_AUTH_TOKEN` | x.com Cookie `auth_token` | 见下方 Cookie 导出 |
| `TWITTER_CT0` | x.com Cookie `ct0` | 同上 |
| `HTTPS_PROXY` | 可选代理 | **先不配**；Actions 抓 X 失败再加 |

#### 导出 X Cookie

1. 浏览器登录 https://x.com  
2. 扩展 Cookie-Editor，或 DevTools → Application → Cookies  
3. 复制 `auth_token`、`ct0` 的值  
4. 粘贴到 Secrets（**不要**写进代码、**不要**发到聊天）

### 2️⃣ 打开 GitHub Pages

打开：  
https://github.com/DoTrungHuy/X-daily-digest/settings/pages

选择：

- Source：**GitHub Actions**

不要再选择旧的：

```text
Deploy from a branch → main → /docs
```

改成 GitHub Actions 后，网站发布由 `.github/workflows/daily.yml` 里的 `deploy-pages` job 完成。

几分钟后访问：  
**https://dotrunghuy.github.io/X-daily-digest/**

### 3️⃣ 触发一次流水线（可选但建议）

打开 Actions：  
https://github.com/DoTrungHuy/X-daily-digest/actions

- 选 workflow **Daily X Digest**
- **Run workflow** → 选择要验证的分支 → 等跑完
- 在 PR 分支上先保持 `deploy_pages=false`，验证生成和 commit
- 如果要在 PR 分支上也验证网站部署，需要先在 `Settings → Environments → github-pages` 允许该分支部署，再用 `deploy_pages=true` 重新运行
- 合并后在 `main` 上运行，会执行完整的 commit + deploy

之后每天 **UTC 00:17 ≈ 北京/新加坡 08:17** 自动跑。

### 4️⃣ 改「想看谁」

编辑 [`config/accounts.yaml`](./config/accounts.yaml)（账号 + 搜索词），commit 即可。  
默认是 CS / AI 向列表，可随时精简或加号。

---

## 💻 本机试跑（可选）

适合在本地验证 Cookie / DeepSeek 是否正常：

```powershell
cd 你的仓库目录
pip install -r requirements.txt

$env:DEEPSEEK_API_KEY="你的key"
$env:TWITTER_AUTH_TOKEN="你的auth_token"
$env:TWITTER_CT0="你的ct0"

# 建议 Python 3.10+（仓库用 3.12 验证过）
python scripts/run_daily.py
```

只重建前端：

```powershell
python scripts/build_site.py
# 打开 docs/index.html 预览，或推送后看 Pages
```

---

## 📁 目录速览

```text
config/accounts.yaml      # 抓取谁、搜什么
src/                      # 抓取 / DeepSeek / 写 digest
scripts/run_daily.py      # 每日入口（Actions 也调它）
scripts/build_site.py     # digests → docs 静态站
prompts/digest_system.md  # 策展 system prompt
digests/                  # 每日 .md 原文
docs/                     # 🌐 静态站文件（作为 Pages artifact 部署）
.github/workflows/daily.yml
```

更细的安装与排错：[`docs/SETUP.md`](./docs/SETUP.md)  
可行性与架构说明：[`docs/FEASIBILITY_AND_PLAN.md`](./docs/FEASIBILITY_AND_PLAN.md)

---

## 🖥️ 站点界面怎么读

| 内容块 | 页面上是什么 |
|--------|----------------|
| **HOOK** | 顶部今日总览 |
| **META** | 时间窗 / 条目数 / 信号强度等标签 |
| **ITEM** | 卡片：标题、类别、原文摘录、实用点、来源链接 |
| **CLOSE** | 「今日只看一条」推荐 |
| 类别筛选 | 日页上可按「大佬官方 / 工具更新…」过滤 |

界面风格：**Linear 系冷静暗色 + 编辑型 Newsletter**（单栏阅读、列表归档、侧栏目录），优先可读与信息密度，不做电影级落地页动效。

---

## 🔧 常见问题

| 问题 | 处理 |
|------|------|
| 站点 404 | 确认 Pages Source 选了 `GitHub Actions`，并检查 `Deploy to GitHub Pages` 是否成功 |
| PR 分支一运行就失败 | 多半是 `github-pages` 环境不允许该分支部署；先用 `deploy_pages=false` 验证 commit，或到 Environments 里允许该分支后再部署 |
| 页面很旧 / 样式不对 | 强刷 `Ctrl+F5`；检查 Actions 是否成功完成 deploy-pages |
| 仓库有新 commit 但网站没变 | 看 Actions 里的 `Deploy to GitHub Pages`，不要只看 commit |
| Actions 抓 X 失败 | Cookie 过期则重导 Secrets；仍失败再试 `HTTPS_PROXY`（策略 A1） |
| DeepSeek 报错 | 检查 `DEEPSEEK_API_KEY` 余额与权限 |
| 本机 `python` 太旧 | 用 Python 3.10+（例如 `C:\Python\Python312\python.exe`） |

---

## 📝 备注

这是我自己搭的日更精读流水线，方便关机也能自动更新。  
文中引用的 X 推文仍归原作者；Cookie 和 API Key 只放在 GitHub Secrets 里，不要写进代码或 commit。
