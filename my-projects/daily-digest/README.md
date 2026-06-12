# Daily Digest — 信息聚合日报

自动采集多源内容、LLM 分类整理、生成结构化日报。支持定时调度和 Telegram 推送。

## 数据源

| 来源 | 类型 | 需要 |
|------|------|------|
| Hacker News | API | 网络 |
| GitHub Trending | API | 网络 |
| 知乎热榜 | API | 网络 |
| RSS 订阅源 (Dev.to, 机器之心, InfoQ等) | RSS | feedparser |
| 自定义网页 | HTML解析 | beautifulsoup4 |

## 两种生成模式

| 模式 | 命令 | 说明 |
|------|------|------|
| 📝 简易模式 | `--simple` | 按来源分组列出，零成本 |
| 🧠 LLM 模式 | 默认 | AI 分类、提炼、推荐，需要 API key |

## 快速开始

```bash
cd daily-digest
pip install -r requirements.txt
cp .env.example .env  # 可选，简易模式不需要

# 简易模式立即生成 (无需API key)
python -m daily_digest now --simple

# LLM 增强模式
python -m daily_digest now -p full

# 保存 + 推送到 Telegram
python -m daily_digest now -o ./output -t $BOT_TOKEN -c $CHAT_ID
```

## 定时调度

```bash
# 每天8点运行
python -m daily_digest schedule --cron "0 8 * * *" --now

# 每2小时运行
python -m daily_digest schedule --interval 7200
```

## 预设采集计划

- `tech` — Hacker News + GitHub Trending + Dev.to
- `china` — 知乎热榜 + InfoQ + 机器之心
- `full` — 以上全部 + RSS

## 项目结构

```
daily-digest/
├── daily_digest/
│   ├── sources.py      # 多源采集 (HN, GitHub, 知乎, RSS, 自定义)
│   ├── digest.py       # LLM/简易 日报生成
│   ├── scheduler.py    # 定时调度
│   ├── notify.py       # Telegram 推送
│   ├── cli.py          # CLI
│   └── __main__.py     # 入口
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT
