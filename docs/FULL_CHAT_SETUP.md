# 方法 1：登录态抓取 Grok Chat 全文

## 为什么需要这一步

Grok Tasks 邮件只有预览 + **Continue reading** → `https://grok.com/chat/<id>`。  
全文在 **登录后的** chat 页里，邮箱 API 拿不到。

## 一次性配置

```powershell
cd "D:\github项目\grok-daily-digest"
C:\Python\Python312\python.exe -m pip install -r requirements.txt
C:\Python\Python312\python.exe -m playwright install chromium

# 打开浏览器，登录 grok.com（用收 gork-daily 的账号）
C:\Python\Python312\python.exe scripts\grok_login.py
```

登录成功看到 Grok 主界面后，回到终端 **按 Enter**。  
会生成项目根目录 `grok_auth.json`（已 gitignore，勿提交）。

## 每日抓取（邮件预览 + 全文）

```powershell
C:\Python\Python312\python.exe scripts\run_daily.py --force
```

成功时日志类似：

```text
Chat   : https://grok.com/chat/...
Content source: grok_chat_full
Full text length: 3000+ chars
```

`digests/YYYY-MM-DD.md` 中：

- **Content source**: `grok_chat_full`
- 正文为完整 chat 文本
- 仍保留邮件预览小节 + chat 链接

## 仅邮件预览（不抓 chat）

```powershell
C:\Python\Python312\python.exe scripts\run_daily.py --skip-full-chat
```

## 会话过期

若提示 private / sign in / 文本过短：

```powershell
C:\Python\Python312\python.exe scripts\grok_login.py
C:\Python\Python312\python.exe scripts\run_daily.py --force
```

## 调试

显示浏览器窗口：

```powershell
C:\Python\Python312\python.exe scripts\run_daily.py --force --headed
```

## GitHub Actions 注意

Actions 默认**没有**你的 `grok_auth.json`。  
全文抓取目前以 **本机定时** 为主；要把 cookie 放进 Secrets 可以后续做，且 cookie 会过期需定期更新。

建议：本机任务计划程序在 15:20 跑 `run_daily.py`，成功后再 `git push` digests（或另做本机 push 脚本）。
