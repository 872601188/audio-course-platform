# OpenClaw 学习助理 MCP Server

音频课程平台的 OpenClaw MCP Server，让 OpenClaw AI 助手成为你的个人学习助理。

## 功能

- `get_courses` - 获取课程列表及进度
- `get_learning_progress` - 获取总体学习进度
- `get_learning_history` - 获取学习历史
- `get_learning_stats` - 获取学习统计
- `get_daily_reminder` - 获取每日/每周督促提醒
- `create_study_plan` - 创建学习计划
- `get_study_plan` - 获取当前计划
- `update_study_plan` - 更新计划状态
- `update_learning_progress` - 更新学习进度

## 安装

```bash
cd mcp-server
pip install -e .
```

## 配置

### 1. 在学习平台生成 API Token

登录平台 → 管理后台 → OpenClaw 集成 → 生成 Token

每个 Token 自动绑定到生成它的用户账号，无需额外配置 User ID。

### 2. OpenClaw 配置

编辑 OpenClaw 配置文件（通常为 `~/.openclaw/config.json`）：

```json
{
  "mcp": {
    "servers": {
      "audio-learning": {
        "command": "python",
        "args": ["-m", "openclaw_learning_server.server"],
        "env": {
          "LEARNING_API_URL": "http://localhost:5000",
          "LEARNING_API_TOKEN": "your-generated-token"
        }
      }
    }
  }
}
```

### 3. 重启 OpenClaw

```bash
openclaw restart
```

## 使用示例

在 OpenClaw 聊天中：

```
> 我今天该学什么？
[OpenClaw 调用 get_daily_reminder]
"你今天的目标是30分钟，目前已学12.5分钟。
 建议优先完成《Python入门》，只差15分钟就能学完！"

> 帮我制定本周学习计划
[OpenClaw 调用 get_courses + get_learning_progress + create_study_plan]
"根据你的进度，本周建议：
 1. 完成《Python入门》（剩余35%）
 2. 每天15分钟复习《数据结构》（已8天未学）
 已为你创建学习计划。"
```
