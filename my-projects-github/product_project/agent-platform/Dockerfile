FROM python:3.11-slim

LABEL org.opencontainers.image.title="Agent Platform"
LABEL org.opencontainers.image.description="生产级 AI Agent 平台"

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ app/
COPY workspace/ workspace/

# 创建会话目录
RUN mkdir -p workspace/.sessions

# 环境变量默认值
ENV HOST=0.0.0.0
ENV PORT=8000
ENV MODEL_ID=claude-sonnet-4-6

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
