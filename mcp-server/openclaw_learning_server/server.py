#!/usr/bin/env python3
"""
OpenClaw Learning Assistant MCP Server
通过 stdio 与 OpenClaw 通信，暴露学习平台相关 Tools。

环境变量：
    LEARNING_API_URL    - 后端 API 地址（默认 http://localhost:5000）
    LEARNING_API_TOKEN  - OpenClaw API Token（每个 Token 已绑定用户，无需额外传 User-ID）

OpenClaw 配置示例：
    {
      "mcp": {
        "servers": {
          "audio-learning": {
            "command": "python",
            "args": ["-m", "openclaw_learning_server.server"],
            "env": {
              "LEARNING_API_URL": "http://localhost:5000",
              "LEARNING_API_TOKEN": "your-token"
            }
          }
        }
      }
    }
"""
import sys
import os

# 将项目目录加入路径，确保能 import
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
from openclaw_learning_server.client import LearningAPIClient
from openclaw_learning_server.tools import register_tools


mcp = FastMCP("audio-learning-assistant")


def main():
    api_url = os.environ.get('LEARNING_API_URL', 'http://localhost:5000')
    api_token = os.environ.get('LEARNING_API_TOKEN', '')

    if not api_token:
        print("Error: LEARNING_API_TOKEN must be set", file=sys.stderr)
        sys.exit(1)

    client = LearningAPIClient(base_url=api_url, token=api_token)
    register_tools(mcp, client)

    # stdio 模式下运行 MCP Server
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
