"""演示模式 — 无需 browser-use 和 API key 也能运行的样例数据.

用真实风格的模拟数据展示完整流程: 搜索 → 提取 → 匹配 → 报告.
"""

from .models import Resume, JobListing, JobSearchResult, MatchResult, MatchReport

# ---------------------------------------------------------------------------
# 模拟简历
# ---------------------------------------------------------------------------

SAMPLE_RESUME = Resume(
    name="张三",
    email="zhangsan@example.com",
    phone="13800000000",
    summary="3年后端开发经验，熟悉Python/Go，有微服务和分布式系统经验",
    skills=[
        "Python", "Go", "FastAPI", "Django", "Docker",
        "Kubernetes", "PostgreSQL", "Redis", "gRPC",
        "Git", "Linux", "CI/CD", "AWS (EC2, S3, Lambda)",
    ],
    experiences=[
        {
            "title": "后端开发工程师",
            "company": "某互联网公司",
            "duration": "2022-至今 (2年)",
            "description": "负责核心API服务开发，日请求量1000万+。主导微服务拆分，将单体应用拆分为12个微服务。引入CI/CD流水线，部署效率提升80%。"
        },
        {
            "title": "Python开发实习生",
            "company": "某科技创业公司",
            "duration": "2021-2022 (1年)",
            "description": "参与自动化测试平台开发，使用FastAPI + PostgreSQL。编写了300+测试用例。"
        },
    ],
    education=[
        {"degree": "计算机科学 本科", "school": "某985大学", "year": "2021"},
    ],
)

# ---------------------------------------------------------------------------
# 模拟职位数据
# ---------------------------------------------------------------------------

SAMPLE_JOBS = [
    JobListing(
        title="高级Python后端工程师",
        company="字节跳动",
        location="北京",
        salary="30K-50K",
        url="https://example.com/job/1",
        description="负责字节跳动核心业务后端开发。要求: 3年以上Python开发经验，熟悉FastAPI/Django，掌握MySQL/PostgreSQL，有微服务架构设计经验，熟悉Docker/K8s，有高并发系统经验优先。",
        source="linkedin",
        tags=["Python", "FastAPI", "微服务", "K8s"],
    ),
    JobListing(
        title="Python开发工程师",
        company="阿里巴巴",
        location="杭州",
        salary="25K-45K",
        url="https://example.com/job/2",
        description="参与电商平台后端开发。要求: 2年以上Python经验，熟悉至少一个Web框架，有MySQL调优经验，了解Redis。加分: Go语言经验，有中间件开发经验。",
        source="linkedin",
        tags=["Python", "MySQL", "Redis"],
    ),
    JobListing(
        title="全栈工程师 (偏后端)",
        company="美团",
        location="北京/上海",
        salary="28K-48K",
        url="https://example.com/job/3",
        description="负责商家端全栈开发。要求: 熟悉Python或Go，有React/Vue前端经验，掌握数据库设计，有系统设计能力。",
        source="indeed",
        tags=["Python", "Go", "React", "全栈"],
    ),
    JobListing(
        title="AI应用开发工程师",
        company="MiniMax",
        location="北京",
        salary="35K-60K",
        url="https://example.com/job/4",
        description="开发基于大模型的AI应用。要求: 3年以上Python经验，熟悉FastAPI异步编程，有LLM API调用经验 (OpenAI/Claude等)，了解RAG和Agent架构，有Prompt Engineering经验。",
        source="linkedin",
        tags=["Python", "FastAPI", "LLM", "RAG"],
    ),
    JobListing(
        title="Go后端开发工程师",
        company="腾讯",
        location="深圳",
        salary="30K-55K",
        url="https://example.com/job/5",
        description="负责腾讯云核心服务开发。要求: 3年以上Go开发经验，熟悉微服务架构，有分布式系统设计经验，掌握常用中间件。了解容器和K8s。",
        source="linkedin",
        tags=["Go", "微服务", "分布式", "K8s"],
    ),
    JobListing(
        title="Python数据分析工程师",
        company="小红书",
        location="上海",
        salary="20K-35K",
        url="https://example.com/job/6",
        description="负责用户行为数据分析。要求: 熟悉Python数据分析栈 (pandas/numpy)，有SQL经验，了解数据可视化。加分: 有推荐系统经验。",
        source="indeed",
        tags=["Python", "数据分析", "SQL"],
    ),
    JobListing(
        title="平台开发工程师 (Python)",
        company="米哈游",
        location="上海",
        salary="28K-50K",
        url="https://example.com/job/7",
        description="参与游戏平台后端开发。要求: 3年以上Python开发经验，熟悉异步编程和FastAPI，有消息队列(Kafka/RabbitMQ)使用经验，了解监控和告警系统。",
        source="glassdoor",
        tags=["Python", "FastAPI", "消息队列", "异步"],
    ),
    JobListing(
        title="运维开发工程师",
        company="华为",
        location="深圳/东莞",
        salary="25K-40K",
        url="https://example.com/job/8",
        description="负责内部DevOps平台开发。要求: 熟悉Python或Go，有CI/CD经验，了解Docker和K8s，熟悉Linux系统管理。有Terraform/Ansible经验优先。",
        source="linkedin",
        tags=["Python", "Go", "DevOps", "K8s"],
    ),
]


def create_demo_search_result() -> JobSearchResult:
    return JobSearchResult(
        keyword="Python后端",
        location="",
        total_found=8,
        listings=SAMPLE_JOBS,
    )


def create_demo_resume() -> Resume:
    return SAMPLE_RESUME


# ---------------------------------------------------------------------------
# 演示匹配 — 规则评分 (不需要 LLM API)
# ---------------------------------------------------------------------------

def demo_match(resume: Resume, job: JobListing) -> MatchResult:
    """基于规则的匹配评分 — 不需要 API key，立即出结果."""
    resume_text = resume.to_text().lower()
    job_text = f"{job.title} {job.description} {','.join(job.tags)}".lower()

    # 技能匹配
    matched_skills = [s for s in resume.skills if s.lower() in job_text]
    skill_score = min(50, len(matched_skills) * 10)

    # 经验年限匹配
    exp_years = 3  # 从简历推断
    experience_score = min(20, exp_years * 6)

    # 关键词匹配
    keywords = ["python", "fastapi", "微服务", "docker", "k8s", "kubernetes",
                "异步", "高并发", "数据库", "redis", "go", "aws", "后端"]
    kw_matches = sum(1 for kw in keywords if kw in resume_text and kw in job_text)
    keyword_score = min(30, kw_matches * 5)

    # 缺失技能
    all_job_skills = [s for s in resume.skills if s.lower() not in job_text.lower()]
    missing = [s for s in job.tags if s.lower() not in resume_text.lower()]

    overall = skill_score + experience_score + keyword_score

    # 推荐等级
    if overall >= 80:
        recommendation = "强推"
    elif overall >= 60:
        recommendation = "推荐"
    elif overall >= 40:
        recommendation = "可投"
    else:
        recommendation = "不推荐"

    return MatchResult(
        job=job,
        overall_score=overall,
        skill_match=matched_skills,
        skill_gaps=missing,
        experience_match=f"你有{exp_years}年后端经验, 与{job.title}的年限要求{'匹配' if exp_years >= 3 else '略有差距'}",
        strengths=[f"熟悉{s}" for s in matched_skills[:3]],
        suggestions="建议在简历中补充: " + ", ".join(missing[:3]) if missing else "简历已经很匹配",
        apply_recommendation=recommendation,
    )


def demo_match_batch(resume: Resume | None = None) -> MatchReport:
    """演示模式完整流程."""
    resume = resume or create_demo_resume()
    search_result = create_demo_search_result()

    matches = [demo_match(resume, job) for job in search_result.listings]

    return MatchReport(
        resume=resume,
        search_result=search_result,
        matches=matches,
    )
