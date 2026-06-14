# ============================================================
# Coding Agent Pro — 后端 Docker 镜像
# ============================================================

FROM python:3.11-slim

LABEL org.opencontainers.image.title="Coding Agent Pro"
LABEL org.opencontainers.image.description="基于 AutoGen 多 Agent 协作的生产级软件研发平台"

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY app/ app/

# 创建数据目录
RUN mkdir -p /app/workspace/artifacts /app/workspace/versions /app/workspace/logs

# 环境变量
ENV HOST=0.0.0.0
ENV PORT=8000
ENV REDIS_URL=redis://redis:6379

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
