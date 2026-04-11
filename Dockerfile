# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=1

WORKDIR /app

# 基础依赖（如需编译或字体渲染，可在此添加）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 仅复制依赖文件以优化缓存
COPY requirements.txt ./

# 如需选择特定环境的依赖，可改为 COPY requirements_run_dev.txt 并安装
RUN pip install -r requirements.txt

# 复制项目源码
COPY . .

EXPOSE 8000

# 默认启动 FastAPI 应用（app.py 中的 app 对象）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]



