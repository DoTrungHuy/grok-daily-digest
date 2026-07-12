# X Daily Digest

**免费读 X（Cookie / twitter-cli）→ DeepSeek 完整精读 → GitHub Pages 日更。**

电脑可关机 · 不付 X 官方 API · Grok Tasks 已弃用

## 结构

```text
config/accounts.yaml     # 账号与搜索（默认可改）
src/
  x_fetch.py             # 采集 X
  deepseek_client.py     # 总结
  digest_writer.py       # 写 digests/
  paths.py
scripts/
  run_daily.py           # 唯一入口
  build_site.py          # 生成 docs 站点
prompts/digest_system.md # DeepSeek system prompt
digests/                 # 每日 md
x_raw/                   # 原始推文 JSON（gitignore）
docs/                    # Pages：index.html + 日页 + 说明 md
.github/workflows/daily.yml
```

## 配置与运行

见 **[docs/SETUP.md](./docs/SETUP.md)**。

计划书：**[docs/FEASIBILITY_AND_PLAN.md](./docs/FEASIBILITY_AND_PLAN.md)**

## 你要做的（一次）

1. 配置 Secrets：`DEEPSEEK_API_KEY`、`TWITTER_AUTH_TOKEN`、`TWITTER_CT0`  
2. Pages → `main` / **docs**  
3. （可选）本机先 `python scripts/run_daily.py` 验证  
4. Actions 每天 **08:00 北京时间** 自动跑  

代理策略：**先直连测，失败再考虑买**（A1）。
