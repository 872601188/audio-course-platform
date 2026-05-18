# 变更日志

## 2026-05-18

- 新增 OpenClaw MCP Server（9 个 Tools）
- 新增 OpenClawToken / StudyPlan 模型
- 新增 openclaw.py 路由（12+ 接口）
- 新增个人设置页面 settings.html
- 新增 PUT /api/me 更新个人信息接口
- User 模型新增 phone 字段
- Token 支持有效期（1/3/6 个月）
- Token 支持 9 项细粒度权限控制
- 导航栏改为下拉菜单设计
- 简化认证：仅需 X-OpenClaw-Token
- 修复 .env Docker 路径问题
- 修复配置指南链接 404 问题
