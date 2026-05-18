#!/bin/bash
# 服务器部署脚本（在服务器上执行）
# 由于服务器无 git，通过下载 GitHub tarball 更新代码

set -e

PROJECT_DIR="/opt/audio-course"
BACKUP_DIR="/opt/backups/audio-course-$(date +%Y%m%d-%H%M%S)"
DB_FILE="$PROJECT_DIR/backend/instance/audio_course.db"
TARBALL_URL="https://github.com/872601188/audio-course-platform/archive/refs/heads/main.tar.gz"

echo "=== 开始部署 ==="

# 1. 备份数据库
echo "[1/6] 备份数据库..."
mkdir -p "$BACKUP_DIR"
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_DIR/"
    echo "数据库已备份到 $BACKUP_DIR"
fi

# 2. 下载最新代码
echo "[2/6] 下载最新代码..."
cd /tmp
rm -rf audio-course-platform-main main.tar.gz
curl -L -o main.tar.gz "$TARBALL_URL"
tar -xzf main.tar.gz

# 3. 替换代码（保留 uploads 和数据库）
echo "[3/6] 更新代码文件..."
if [ -d "$PROJECT_DIR/backend/uploads" ]; then
    cp -r "$PROJECT_DIR/backend/uploads" /tmp/audio-course-uploads-backup/
fi

rm -rf "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cp -r /tmp/audio-course-platform-main/* "$PROJECT_DIR/"

if [ -d "/tmp/audio-course-uploads-backup" ]; then
    cp -r /tmp/audio-course-uploads-backup/* "$PROJECT_DIR/backend/uploads/"
    rm -rf /tmp/audio-course-uploads-backup
fi

# 4. 安装依赖
echo "[4/6] 安装依赖..."
cd "$PROJECT_DIR"
pip3.11 install -r backend/requirements.txt

# 4.5. 配置 DeepSeek AI 环境变量
echo "[4.5/6] 配置 AI 环境变量..."
cat > "$PROJECT_DIR/.env" << 'EOF'
JWT_SECRET_KEY=audio-course-platform-secret-key-change-me
SQLITE_DB_PATH=/opt/audio-course/backend/instance/audio_course.db
UPLOAD_FOLDER=/opt/audio-course/backend/uploads
AI_API_KEY=sk-ff9cad1d901a40919d835d951455d714
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
PORT=5000
EOF

# 5. 数据库迁移
echo "[5/6] 执行数据库迁移..."
cd "$PROJECT_DIR/backend"
python3.11 -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migrate_db import migrate
migrate()
"

# 6. 重启服务
echo "[6/6] 重启服务..."
pkill -f 'python3.*backend.app' || true
sleep 2
cd "$PROJECT_DIR"
python3 -m backend.app > /tmp/flask.log 2>&1 &
echo "Flask 已启动，PID: $!"
sleep 2
cat /tmp/flask.log | tail -n 5

echo "=== 部署完成 ==="
