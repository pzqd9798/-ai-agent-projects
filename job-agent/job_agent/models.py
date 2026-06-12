"""数据模型 — JobListing, Resume, MatchResult, Report."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobListing:
    """职位信息."""
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    salary: str = ""
    source: str = ""          # 来源网站
    posted_date: str = ""
    tags: list[str] = field(default_factory=list)  # 技能标签


@dataclass
class Resume:
    """简历信息."""
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""         # 个人简介
    skills: list[str] = field(default_factory=list)
    experiences: list[dict] = field(default_factory=list)  # [{title, company, duration, description}]
    education: list[dict] = field(default_factory=list)    # [{degree, school, year}]
    raw_text: str = ""        # 原始简历文本

    def to_text(self) -> str:
        """序列化为 LLM 可读的文本."""
        lines = [f"姓名: {self.name or '未提供'}"]
        if self.summary:
            lines.append(f"简介: {self.summary}")
        if self.skills:
            lines.append(f"技能: {', '.join(self.skills)}")
        if self.experiences:
            lines.append("工作经历:")
            for exp in self.experiences:
                lines.append(f"  - {exp.get('title', '')} @ {exp.get('company', '')} ({exp.get('duration', '')})")
                if exp.get('description'):
                    lines.append(f"    {exp['description']}")
        if self.education:
            lines.append("教育背景:")
            for edu in self.education:
                lines.append(f"  - {edu.get('degree', '')} @ {edu.get('school', '')} ({edu.get('year', '')})")
        return "\n".join(lines)


@dataclass
class MatchResult:
    """职位匹配结果."""
    job: JobListing
    overall_score: float     # 0-100
    skill_match: list[str] = field(default_factory=list)       # 匹配的技能
    skill_gaps: list[str] = field(default_factory=list)        # 缺失的技能
    experience_match: str = ""   # 经验匹配分析
    strengths: list[str] = field(default_factory=list)         # 你的优势
    suggestions: str = ""        # 简历优化建议
    apply_recommendation: str = ""  # 推荐投递程度: 强推/推荐/可投/不推荐


@dataclass
class JobSearchResult:
    """搜索结果."""
    keyword: str
    location: str = ""
    total_found: int = 0
    listings: list[JobListing] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MatchReport:
    """完整的匹配报告."""
    resume: Resume
    search_result: JobSearchResult
    matches: list[MatchResult] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def sorted_matches(self) -> list[MatchResult]:
        return sorted(self.matches, key=lambda m: m.overall_score, reverse=True)

    def top_matches(self, n: int = 5) -> list[MatchResult]:
        return self.sorted_matches()[:n]
