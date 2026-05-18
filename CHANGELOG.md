# 变更日志

## 2026-05-18

### 新增：AI 学习计划与执行追踪
- 扩展 StudyPlan 模型：支持 `ai_generated`、`schedule`（JSON 时段安排）、`total_expected_minutes`、`learning_goal`
- 新增 PlanExecution 模型：每个时段独立追踪（pending / in_progress / completed / skipped）
- 新增 `backend/services/ai_scheduler.py`：LLM 生成学习计划，无 API Key 时自动回退到本地规则引擎
- 新增 OpenClaw API 端点：
  - `POST /openclaw/plan/ai-generate` — AI 生成计划
  - `GET /openclaw/plan/execution` — 获取执行列表
  - `POST /openclaw/plan/execution/<id>` — 更新执行状态
  - `GET /openclaw/plan/progress` — 获取总体进度
  - `POST /openclaw/plan/sync` — 根据 StudyLog 自动同步实际学习时长
- MCP Server 新增 4 个 Tools：
  - `generate_ai_study_plan` — AI 生成计划
  - `get_plan_execution` — 查询执行详情
  - `get_plan_progress` — 查询完成进度
  - `sync_plan_execution` — 同步学习记录
- 前端 settings.html 新增 AI 学习计划面板：
  - AI 生成计划弹窗（支持选择课程、设置每日时间、计划天数、学习目标）
  - 计划执行追踪（列表/日历双视图）
  - 手动同步按钮
  - 状态管理（完成/跳过/重置）
- 新增 `backend/migrate_db.py` 数据库迁移脚本（SQLite ALTER TABLE）

### 前期已完成
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
