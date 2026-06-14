# Web Agent — 智能网页信息采集工具

基于 LLM 的智能网页信息采集 Agent，支持静态 HTTP 和浏览器两种提取模式，自动生成结构化摘要报告。

## 核心特性

- 🌐 **双模提取** — 静态 HTTP (BeautifulSoup) + 浏览器模式 (browser-use, JS渲染)
- 🧠 **LLM 智能摘要** — 自动识别页面类型、提取关键要点、实体和情感倾向
- 📋 **批量并发处理** — 多 URL 并发采集，支持从文件读取 URL 列表
- 📊 **多格式输出** — Rich终端、JSON、Markdown
- 🔒 **域名安全隔离** — 浏览器模式锁定目标域名

## 快速开始

```bash
cd web-agent
pip install -r requirements.txt
cp .env.example .env  # 填入 ANTHROPIC_API_KEY
```

## 使用方式

### CLI

```bash
# 单个网页摘要
python -m web_agent fetch https://news.ycombinator.com

# JSON 输出
python -m web_agent fetch https://example.com -o json

# 浏览器模式 (JS渲染页面)
python -m web_agent fetch https://example.com --browser

# 自定义分析提示词
python -m web_agent fetch https://example.com -p "提取所有产品价格"

# 批量处理
python -m web_agent batch https://a.com https://b.com https://c.com

# 从文件批量处理
python -m web_agent batch --file urls.txt -w 5

# 保存结果
python -m web_agent fetch https://example.com -s report.md
python -m web_agent batch --file urls.txt -s results.json -o json
```

### Python API

```python
from web_agent.extractor import extract_static
from web_agent.summarizer import summarize

# 提取
page = extract_static("https://example.com")

# 摘要
report = summarize(page)
print(report.summary)
print(report.key_points)
print(report.to_markdown())

# 批量
from web_agent.batch import process_batch
reports = process_batch(["https://a.com", "https://b.com"])
```

### 集成到 Agent Platform

```python
# 在 agent-platform 中作为工具使用
from web_agent.extractor import extract_static
from web_agent.summarizer import summarize

def tool_web_summary(url: str) -> str:
    page = extract_static(url)
    report = summarize(page)
    return report.to_markdown()
```

## 输出示例

```markdown
# Hacker News

**URL**: https://news.ycombinator.com
**类型**: 社交 | **立场**: 中性 | **方法**: static

## 📝 摘要

Hacker News 首页当前展示了约30条科技新闻...

## 🔑 关键要点

- 热点讨论: AI 模型安全性新进展
- Show HN: 一个开源的个人知识管理工具
- ...
```

## 技术栈

- Python 3.11+ · Anthropic Claude API
- httpx + BeautifulSoup4 (静态提取)
- browser-use (浏览器提取, 可选)
- Rich (终端美化)

## License

MIT
