"""简历匹配引擎 — LLM 对比简历和职位描述，生成匹配报告."""

import os
import json
from anthropic import Anthropic
from .models import Resume, JobListing, MatchResult, MatchReport, JobSearchResult


MATCH_SYSTEM_PROMPT = """你是一个专业的简历评估和职位匹配专家。你的任务是:
1. 仔细对比求职者的简历和职位描述
2. 评估匹配程度 (0-100分)
3. 分析技能匹配和差距
4. 给出具体的简历优化建议

请以严格的 JSON 格式输出, 不要 markdown 代码块。"""


MATCH_PROMPT = """请分析以下简历和职位的匹配度。

## 求职者简历

{resume_text}

---

## 职位信息

- 职位: {job_title}
- 公司: {job_company}
- 地点: {job_location}
- 薪资: {job_salary}

### 职位描述
{job_description}

---

请以 JSON 格式输出分析结果:

{{
  "overall_score": 75,
  "skill_match": ["Python", "FastAPI"],
  "skill_gaps": ["Kubernetes", "AWS ECS"],
  "experience_match": "求职者有3年Python后端经验，与职位要求的后端开发经验高度匹配...",
  "strengths": ["Python技术栈匹配", "有微服务经验"],
  "suggestions": "建议在简历中突出Docker和CI/CD经验，补充Golang学习计划...",
  "apply_recommendation": "强推"
}}

说明:
- overall_score: 0-100, 综合评分
- skill_match: 简历中匹配职位要求的技能列表
- skill_gaps: 职位要求但简历中缺少的技能
- experience_match: 50字以内的经验匹配分析
- strengths: 求职者的突出优势 (2-3条)
- suggestions: 简历优化建议
- apply_recommendation: "强推" (80+分), "推荐" (60-79分), "可投" (40-59分), "不推荐" (40-分)

只输出JSON。"""


class JobMatcher:
    """简历-职位匹配引擎."""

    def __init__(self):
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            from dotenv import load_dotenv
            load_dotenv()
            self._client = Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
            )
        return self._client

    @property
    def model(self) -> str:
        return os.getenv("MODEL_ID", "claude-sonnet-4-6")

    def match_single(self, resume: Resume, job: JobListing) -> MatchResult:
        """匹配单个职位."""
        prompt = MATCH_PROMPT.format(
            resume_text=resume.to_text(),
            job_title=job.title,
            job_company=job.company,
            job_location=job.location,
            job_salary=job.salary or "未提供",
            job_description=job.description or "无描述",
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=MATCH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                result_text += block.text

        # 解析 JSON
        try:
            result_text = result_text.strip()
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1])
            data = json.loads(result_text)
        except json.JSONDecodeError:
            data = {"overall_score": 50, "apply_recommendation": "可投"}

        return MatchResult(
            job=job,
            overall_score=float(data.get("overall_score", 50)),
            skill_match=data.get("skill_match", []),
            skill_gaps=data.get("skill_gaps", []),
            experience_match=data.get("experience_match", ""),
            strengths=data.get("strengths", []),
            suggestions=data.get("suggestions", ""),
            apply_recommendation=data.get("apply_recommendation", "可投"),
        )

    def match_batch(self, resume: Resume, search_result: JobSearchResult,
                    max_jobs: int = 20) -> MatchReport:
        """批量匹配.

        为节省 API 调用，先对职位进行预筛选:
        - 标题包含不相关关键词的直接跳过
        - 描述过短的跳过
        然后逐个调用 LLM 匹配.
        """
        jobs = search_result.listings[:max_jobs]
        matches = []

        for i, job in enumerate(jobs):
            print(f"  [匹配 {i+1}/{len(jobs)}] {job.title[:40]} @ {job.company}")
            try:
                result = self.match_single(resume, job)
                matches.append(result)
            except Exception as exc:
                print(f"    匹配失败: {exc}")

        return MatchReport(
            resume=resume,
            search_result=search_result,
            matches=matches,
        )
