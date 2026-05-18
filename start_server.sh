#!/bin/bash
cd /root/.openclaw/workspace/audio-course-platform
# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi
python3 -m backend.app > /tmp/flask.log 2>&1 &
echo "PID: $!"
sleep 3
cat /tmp/flask.log
