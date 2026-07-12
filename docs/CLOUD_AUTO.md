# 电脑关机也能全自动（GitHub 云端）

## 你的目标

- 电脑**可以关机**
- 每天 `gork-daily`（约 15:00）生成摘要并发邮件  
- **GitHub Actions** 自动把当天结果写进仓库 `digests/`

## 已配置的定时

| 时间（北京） | 谁 | 做什么 |
|--------------|-----|--------|
| ~15:00 | Grok Tasks `gork-daily` | 生成摘要 → 邮件 |
| **15:30** | GitHub Actions `Daily Grok Digest` | 读 Gmail → 写 digests → commit/push |

对应 cron：`30 7 * * *`（UTC）

手动补跑：仓库 → **Actions** → **Daily Grok Digest** → **Run workflow**

## 云端能拿到什么 / 拿不到什么

| 内容 | 云端能否自动 | 原因 |
|------|----------------|------|
| 当天 Tasks 邮件预览 | ✅ | Gmail API + Secrets |
| 邮件里的 **Continue reading 链接**（当天新对话 uuid） | ✅ | 从 HTML 解析 |
| Grok 网页上的 **完整 8 条正文** | ❌ 默认不做 | 需浏览器登录 + 常被 Cloudflare 拦；云主机没有你的长期 Grok 会话 |

因此 GitHub 上的 `digests/日期.md` 会包含：

1. 邮件预览正文  
2. **当天新 chat 的完整正文链接**（点开、登录 Grok 可看全文）

这是 **电脑关机前提下** 最稳的全自动方案。

## 你需要准备的 Secrets（已有可跳过）

仓库 → Settings → Secrets → Actions：

- `GMAIL_CLIENT_SECRET_JSON`
- `GMAIL_TOKEN_JSON`（含 refresh_token；失效时在本机重授权再更新 Secret）

可选 Variable：

- `GMAIL_QUERY` =  
  `from:noreply@x.ai newer_than:14d -subject:"New login" -subject:security -subject:"xAI account"`

## 和「本机 Playwright 抓全文」的关系

- **不依赖** 电脑开机  
- 本机 `grok_login` / Playwright **不是**这条云端链路的一部分  
- 若将来接受 xAI API 或更复杂的云登录方案，可以再升级「云端全文」

## 验收

1. 电脑关机  
2. 第二天看仓库 `digests/` 是否多了/更新了当天文件  
3. 文件里是否有 **完整正文（Grok 网页）** 链接且 uuid 与当天邮件一致  
