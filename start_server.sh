#!/bin/bash
cd /root/.openclaw/workspace/audio-course-platform
python3 -m backend.app > /tmp/flask.log 2>&1 &
echo "PID: $!"
sleep 3
cat /tmp/flask.log