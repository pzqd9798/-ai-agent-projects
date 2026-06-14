"""报告生成器 — 终端 Rich、Markdown、JSON 格式输出."""

import json
from .models import MatchReport, MatchResult


def to_markdown(report: MatchReport) -> str:
    """生成 Markdown 格式匹配报告."""
    top = report.sorted_matches()
    lines = [
        "# 🎯 求职匹配报告",
        "",
        f"**搜索关键词**: {report.search_result.keyword}",
        f"**匹配职位数**: {report.search_result.total_found}",
        f"**生成时间**: {report.generated_at[:19]}",
        "",
        "---",
        "",
        "## 📋 简历摘要",
        "",
        f"**姓名**: {report.resume.name or '未提供'}",
        f"**技能**: {', '.join(report.resume.skills)}",
        f"**经验**: {len(report.resume.experiences)} 段工作经历",
        "",
        "---",
        "",
        "## 🏆 职位匹配排名",
        "",
    ]

    for i, m in enumerate(top):
        icon = {"强推": "🟢", "推荐": "🟡", "可投": "🟠", "不推荐": "🔴"}.get(
            m.apply_recommendation, "⚪")

        lines.extend([
            f"### {i+1}. {icon} {m.job.title} — 匹配度 {m.overall_score}%",
            "",
            f"| 项目 | 详情 |",
            f"|------|------|",
            f"| **公司** | {m.job.company} |",
            f"| **地点** | {m.job.location} |",
            f"| **薪资** | {m.job.salary or '未提供'} |",
            f"| **来源** | {m.job.source} |",
            f"| **推荐** | **{m.apply_recommendation}** |",
            "",
            "**匹配技能**: " + ", ".join(m.skill_match) if m.skill_match else "无",
            "",
            "**技能差距**: " + ", ".join(m.skill_gaps) if m.skill_gaps else "无",
            "",
            f"**经验分析**: {m.experience_match}",
            "",
            f"**优势**: {'; '.join(m.strengths) if m.strengths else '无'}",
            "",
            f"**建议**: {m.suggestions}",
            "",
            f"**JD摘要**: {m.job.description[:200]}..." if m.job.description else "",
            "",
            "---",
            "",
        ])

    lines.extend([
        "## 📊 统计",
        "",
        f"- 强推: {sum(1 for m in top if m.apply_recommendation == '强推')}",
        f"- 推荐: {sum(1 for m in top if m.apply_recommendation == '推荐')}",
        f"- 可投: {sum(1 for m in top if m.apply_recommendation == '可投')}",
        f"- 不推荐: {sum(1 for m in top if m.apply_recommendation == '不推荐')}",
        "",
        f"平均分: {sum(m.overall_score for m in top)/len(top):.1f}" if top else "",
    ])

    return "\n".join(lines)


def to_json(report: MatchReport) -> str:
    """生成 JSON 格式."""
    return json.dumps({
        "keyword": report.search_result.keyword,
        "total_found": report.search_result.total_found,
        "resume": {
            "name": report.resume.name,
            "skills": report.resume.skills,
            "experiences": report.resume.experiences,
        },
        "matches": [
            {
                "rank": i+1,
                "title": m.job.title,
                "company": m.job.company,
                "location": m.job.location,
                "salary": m.job.salary,
                "score": m.overall_score,
                "skill_match": m.skill_match,
                "skill_gaps": m.skill_gaps,
                "recommendation": m.apply_recommendation,
                "suggestions": m.suggestions,
            }
            for i, m in enumerate(report.sorted_matches())
        ],
    }, ensure_ascii=False, indent=2)


def print_rich(report: MatchReport) -> None:
    """Rich 终端美化输出."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()
        top = report.sorted_matches()

        # 汇总面板
        avg_score = sum(m.overall_score for m in top) / len(top) if top else 0
        summary = (
            f"关键词: {report.search_result.keyword}  |  "
            f"匹配: {len(top)} 个职位  |  "
            f"均分: {avg_score:.0f}"
        )
        console.print(Panel(summary, title="🎯 求职匹配报告"))

        # 排名表
        table = Table(title="职位匹配排名")
        table.add_column("#", style="dim")
        table.add_column("职位")
        table.add_column("公司")
        table.add_column("地点")
        table.add_column("薪资")
        table.add_column("评分")
        table.add_column("推荐")

        for i, m in enumerate(top):
            color_map = {"强推": "green", "推荐": "yellow", "可投": "orange1", "不推荐": "red"}
            color = color_map.get(m.apply_recommendation, "white")

            table.add_row(
                str(i+1),
                m.job.title[:30],
                m.job.company[:15],
                m.job.location[:10],
                m.job.salary[:15] or "-",
                f"{m.overall_score:.0f}",
                f"[{color}]{m.apply_recommendation}[/{color}]",
            )

        console.print(table)

        # 详情
        for i, m in enumerate(top[:3]):
            console.print(f"\n[bold]#{i+1} {m.job.title}[/bold] @ {m.job.company}")
            console.print(f"  匹配技能: {', '.join(m.skill_match) if m.skill_match else '无'}")
            console.print(f"  技能差距: {', '.join(m.skill_gaps) if m.skill_gaps else '无'}")
            console.print(f"  建议: {m.suggestions}")

    except ImportError:
        print(to_markdown(report))
