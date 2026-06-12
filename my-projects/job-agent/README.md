# 求职助手 — 自动搜索职位 & 简历匹配

基于 browser-use + LLM 的自动化求职工具。输入关键词 → 自动搜索职位 → 提取 JD → LLM 匹配简历 → 生成排名报告。

## 两种模式

| 模式 | 命令 | 需要 |
|------|------|------|
| 🎮 演示模式 | `python -m job_agent demo` | 零依赖，立即运行 |
| 🚀 真实搜索 | `python -m job_agent search "Python后端"` | browser-use + API key |

## 演示模式输出示例

```
🎯 求职匹配报告

关键词: Python后端  |  匹配: 8 个职位  |  均分: 66

#  职位                    公司      评分  推荐
 1  高级Python后端工程师      字节跳动     98  强推 🟢
 2  运维开发工程师            华为        83  强推 🟢
 3  Python开发工程师          阿里巴巴     68  推荐 🟡
 4  AI应用开发工程师          MiniMax     63  推荐 🟡
 5  平台开发工程师 (Python)    米哈游       60  推荐 🟡
 6  Go后端开发工程师           腾讯        43  可投 🟠
 7  全栈工程师 (偏后端)        美团        38  不推荐 🔴
 8  Python数据分析工程师       小红书       28  不推荐 🔴
```

## 快速开始

```bash
cd job-agent
pip install -r requirements.txt

# 演示模式 (推荐先试)
python -m job_agent demo

# 保存报告
python -m job_agent demo -s report.md
python -m job_agent demo -o json -s report.json
```

## 真实搜索 (需要 browser-use)

```bash
pip install "browser-use[core]"
cp .env.example .env  # 填入 ANTHROPIC_API_KEY

# 搜索职位
python -m job_agent search "Python后端" -l "北京"

# 指定简历文件
python -m job_agent search "AI工程师" -r my_resume.txt -s report.md

# 多站点搜索
python -m job_agent search "Go开发" --sites "linkedin,indeed" -m 20
```

## Python API

```python
from job_agent.demo import demo_match_batch
from job_agent.reporter import to_markdown

report = demo_match_batch()
print(to_markdown(report))
print(f"Top: {report.top_matches(3)}")
```

## 项目结构

```
job-agent/
├── job_agent/
│   ├── models.py      # 数据模型
│   ├── scraper.py     # 浏览器搜索爬虫
│   ├── matcher.py     # LLM 简历匹配引擎
│   ├── demo.py        # 演示模式 (规则评分)
│   ├── reporter.py    # 报告生成 (Rich/MD/JSON)
│   ├── cli.py         # CLI
│   └── __main__.py    # 入口
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT
