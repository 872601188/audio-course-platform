FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包含音频处理需要的库）
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 创建上传目录
RUN mkdir -p backend/uploads/audio backend/uploads/covers backend/instance

# 设置环境变量
ENV PYTHONPATH=/app
ENV FLASK_APP=backend/app.py
ENV PORT=5000

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "backend/app.py"]
