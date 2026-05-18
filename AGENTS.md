# AGENTS.md — 音频学习平台

> 本文件供 AI Coding Agent 阅读。项目主要文档和代码注释使用中文，因此本文件以中文撰写。

---

## 项目概述

**音频学习平台 (Audio Course Platform)** 是一个基于 Flask + SQLite + TailwindCSS 的音频课程学习系统。

核心功能：
- 批量上传音频（MP3/WAV/OGG/M4A/FLAC/AAC）
- JWT 认证的用户系统，支持管理员 / 学员两种角色
- 课程创建、分类管理、封面图上传
- 断点续播：自动保存并恢复播放进度
- 学习分析：统计学习时长、播放次数，生成个性化建议
- OpenClaw / MCP 集成：通过外部 AI 助手查询学习数据、制定学习计划
- 响应式前端，适配桌面端和移动端

项目由三大组件组成：
1. **backend/** — Flask REST API + 静态文件服务
2. **frontend/** — 纯 HTML + 原生 JavaScript 多页面应用
3. **mcp-server/** — 独立的 MCP Server（Python 包），通过 HTTP 调用 backend

---

## 技术栈

| 层级 | 技术 | 版本 / 说明 |
|------|------|-------------|
| 后端框架 | Flask | 3.0.3 |
| ORM | Flask-SQLAlchemy / SQLAlchemy | 3.1.1 / 2.0.30 |
| 认证 | Flask-JWT-Extended | 4.6.0（Web 前端） |
| CORS | Flask-CORS | 4.0.0 |
| 数据库 | SQLite | 强制使用，单文件 |
| WSGI | Werkzeug / gunicorn | 开发用 Werkzeug，生产可配 gunicorn |
| 环境变量 | python-dotenv | 1.0.1 |
| 图片处理 | Pillow | 10.3.0 |
| 音频元数据 | mutagen | 1.47.0 |
| 云存储 | oss2 | 2.18.3（阿里云 OSS，默认关闭） |
| 前端 | 原生 HTML + JS | 无构建工具、无框架 |
| CSS | TailwindCSS | CDN 引入 |
| MCP Server | mcp (Model Context Protocol) | >=1.27.0，stdio 传输 |
| MCP HTTP 客户端 | httpx | >=0.28.0 |
| Python 版本 | 3.11 ~ 3.12 | 推荐 3.12 |

---

## 项目结构

```
audio-course-platform/
├── backend/
│   ├── app.py                 # 应用工厂 create_app()，静态文件服务
│   ├── models.py              # SQLAlchemy 模型（9 张表）
│   ├── init_db.py             # 初始化数据库：创建表 + 默认账号 + 示例课程
│   ├── migrate_db.py          # 数据库迁移：SQLite ALTER TABLE 添加新列
│   ├── requirements.txt       # Python 依赖（12 个固定版本）
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py            # 注册 / 登录 / 个人信息 / 改密
│   │   ├── courses.py         # 课程 CRUD、搜索、分页、音频排序
│   │   ├── upload.py          # 音频/封面上传、文件读取、批量删除
│   │   ├── player.py          # 收藏、播放进度、学习日志、音频流
│   │   ├── analyze.py         # AI 学习分析、学习统计仪表盘
│   │   └── openclaw.py        # OpenClaw Token / 计划 / 进度 / 历史 / 提醒 / AI 生成
│   └── services/
│       ├── __init__.py
│       ├── openclaw_bridge.py # 学习分析业务逻辑（本地规则引擎）
│       └── ai_scheduler.py    # AI 学习计划生成（LLM + 本地回退）
├── frontend/
│   ├── index.html             # 首页：课程列表
│   ├── login.html             # 登录 / 注册
│   ├── player.html            # 音频播放器
│   ├── favorites.html         # 我的收藏
│   ├── analyze.html           # 学习分析仪表盘
│   ├── admin.html             # 管理员后台：课程管理、上传、OpenClaw Token
│   └── js/
│       ├── api.js             # 统一 API 客户端（fetch 封装）
│       ├── auth.js            # 认证工具、权限检查、格式化函数
│       ├── app.js             # 首页逻辑
│       └── player.js          # 播放器引擎
├── mcp-server/
│   ├── pyproject.toml         # Python 包配置
│   ├── README.md              # MCP 配置说明（中文）
│   └── openclaw_learning_server/
│       ├── __init__.py
│       ├── server.py          # FastMCP 初始化 + stdio 运行入口
│       ├── client.py          # LearningAPIClient：HTTP 调用 backend
│       └── tools.py           # 13 个 MCP Tool 定义
├── Dockerfile
├── docker-compose.yml
├── run_init.sh                # 初始化脚本（含硬编码绝对路径）
├── start_server.sh            # 后台启动脚本（含硬编码绝对路径）
├── .env.example               # 环境变量模板
└── .gitignore
```

---

## 数据库模型

共 9 张表，定义在 `backend/models.py`：

| 模型 | 说明 | 级联删除 |
|------|------|----------|
| `User` | 用户（admin / student） | — |
| `Course` | 课程 | `audio_files` 级联删除 |
| `AudioFile` | 音频文件（归属课程，按 `order_index` 排序） | `playback_progress` 级联删除 |
| `PlaybackProgress` | 用户-音频播放进度 | — |
| `Favorite` | 用户收藏 | — |
| `StudyLog` | 播放/暂停/跳转等原始行为日志 | — |
| `OpenClawToken` | 外部 MCP/CLI 使用的 API Token（SHA-256 存储） | — |
| `StudyPlan` | 学习计划（日/周/AI 生成目标） | — |
| `PlanExecution` | 计划执行追踪（每个时段的预期 vs 实际） | — |

关系：
- `User` 1:N `PlaybackProgress`、`Course`、`Favorite`
- `Course` 1:N `AudioFile`（按 `order_index` 排序）
- `AudioFile` 1:N `PlaybackProgress`

---

## 构建与运行命令

### 本地开发（推荐首次上手）

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r backend/requirements.txt

# 3. 启动服务
python backend/app.py        # 默认运行在 http://localhost:5000

# 4. 初始化数据（另开终端）
python backend/init_db.py    # 创建 admin/admin123、student/student123、3 门示例课程
```

### Docker 部署（生产推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，务必修改 JWT_SECRET_KEY

# 2. 构建并启动
docker-compose up -d

# 3. 初始化数据
docker-compose exec web python backend/init_db.py

# 访问 http://localhost:5000
```

**Docker 持久化卷：**
- `./backend/instance:/app/backend/instance` — SQLite 数据库
- `./backend/uploads:/app/backend/uploads` — 上传的音频和封面

### MCP Server 安装与运行

```bash
cd mcp-server
pip install -e .

# 运行（需配置环境变量）
LEARNING_API_URL=http://localhost:5000 \
LEARNING_API_TOKEN=<你的OpenClawToken> \
LEARNING_USER_ID=<用户ID> \
python -m openclaw_learning_server.server
```

MCP Server 通过 `stdio` 与 OpenClaw Host 通信，所有数据均通过 HTTP 请求访问 `backend/routes/openclaw.py`。

---

## 代码风格与开发约定

### Python 后端

1. **双重导入兼容模式**  
   每个模块顶部都有如下结构，以支持 `python app.py`（CWD = `backend/`）和 `python -m backend.app`（CWD = 项目根目录）两种运行方式：
   ```python
   try:
       from backend.models import db, User, ...
   except ImportError:
       from models import db, User, ...
   ```
   **修改模型或路由导入时，必须保持此兼容模式。**

2. **所有蓝图挂载在 `/api/*` 前缀下**  
   例如 `auth_bp` → `/api/register`、`courses_bp` → `/api/courses`。

3. **模型转字典**  
   每个模型类都提供 `to_dict()` 方法，用于序列化返回给前端。

4. **环境变量优先**  
   所有配置项（DB 路径、上传目录、JWT 密钥、OSS 开关）均从环境变量读取，并带有安全的本地默认值。

5. **无类型注解**  
   代码未使用 Python 类型提示，保持传统动态风格。

### 前端

1. **无构建工具**  
   纯原生 HTML + JavaScript，TailwindCSS 通过 CDN 加载。没有 `package.json`、Vite、Webpack。

2. **多页面应用 (MPA)**  
   每个功能对应独立 HTML 文件（`index.html`、`player.html` 等），非 SPA。

3. **状态管理**  
   认证状态仅存于 `localStorage`，键名为 `access_token` 和 `user`。注意：`admin.html` 的 OpenClaw 区域曾错误使用 `token` 键，存在潜在不一致。

4. **API 封装**  
   所有后端调用统一走 `js/api.js` 的 `apiFetch()` 包装器，自动注入 `Authorization: Bearer <token>`，并在 401 时跳转登录页。

5. **播放器逻辑**  
   `player.js` 使用原生 `<audio>` 元素，自定义控件。进度保存策略：
   - 播放期间每 ~30 秒节流保存一次
   - `beforeunload` 时通过 `navigator.sendBeacon` 发送最终进度
   - 记录 `play`、`pause`、`complete`、`seek` 等行为到 `StudyLog`

---

## 测试说明

**当前项目没有任何自动化测试。**

- 后端：无 `test_*.py`、无 `pytest.ini`、无测试目录。
- 前端：无单元测试或 E2E 测试配置。

测试策略现状：
- 依赖手工测试验证功能。
- `init_db.py` 中的默认账号和示例课程可用于快速手动回归。

如需添加测试，建议：
- 后端引入 `pytest` + `pytest-flask`，在 `backend/tests/` 编写。
- 注意保持双重导入兼容模式，测试启动路径需与工厂函数一致。

---

## 安全注意事项

1. **JWT 密钥**  
   `.env.example` 和 `docker-compose.yml` 中的默认值为 `dev-secret-key-change-in-production`。**生产环境必须覆盖 `JWT_SECRET_KEY`，否则存在严重签名伪造风险。**

2. **SQLite 并发**  
   `backend/app.py` 显式设置 `check_same_thread=False` 以兼容 Flask 多线程请求模型。这在高并发写入场景下存在数据库损坏风险；如需扩展，应迁移至 PostgreSQL/MySQL。

3. **OpenClaw Token 存储**  
   Token 以 SHA-256 哈希存储，生成时仅在前端展示一次明文，之后不可恢复。此设计合理，但需提醒用户妥善保存。

4. **文件上传限制**  
   最大上传 500MB，由 Flask `MAX_CONTENT_LENGTH` 控制。大文件上传可能因网络超时而失败，目前无分片上传机制。

5. **OSS 文件残留**  
   删除课程时，本地文件会被物理删除，但阿里云 OSS 上的对象不会被清理，可能导致存储残留。

6. **无 HTTP Range 请求**  
   音频流不支持 Range 请求，大文件无法高效拖放或断点续传。

7. **脚本硬编码路径**  
   `run_init.sh` 和 `start_server.sh` 包含绝对路径 `/root/.openclaw/workspace/audio-course-platform`，在其他环境中不可直接使用。

---

## 部署架构

```
┌─────────────────────────────────────────┐
│           Docker Container (web)        │
│  ┌─────────────┐    ┌───────────────┐  │
│  │   Flask     │◄──►│   SQLite DB   │  │
│  │  (backend)  │    │ (volume mount)│  │
│  └──────┬──────┘    └───────────────┘  │
│         │                               │
│  ┌──────▼──────┐    ┌───────────────┐  │
│  │  Frontend   │    │ Upload Storage│  │
│  │(HTML/JS/CSS)│    │ (volume mount)│  │
│  └─────────────┘    └───────────────┘  │
└─────────────────────────────────────────┘
              │
              ▼
         Port 5000
```

- **单体架构**：Flask 同时提供 API 和前端静态文件。
- **MCP Server** 作为独立进程运行在容器外（或另一个容器中），通过 HTTP 访问 Flask 的 `/api/openclaw/*` 接口。
- 数据持久化完全依赖 Docker Volume；上传目录和数据库文件均受 `.gitignore` 保护，不会被提交。

---

## 已知问题与限制（基于现有代码）

1. `backend/routes/player.py` 中存在一段未包裹在函数或路由装饰器内的悬空代码（约第 100–130 行），似乎是 `GET /progress/<int:audio_id>` 的遗留实现。
2. AI 学习分析当前完全依赖本地规则引擎（`generate_ai_suggestions`），`build_analysis_prompt()` 仅为占位，未接入任何外部 LLM API。
3. 前端 `admin.html` 的 OpenClaw Token 管理曾使用 `localStorage` 键 `token`，与其他页面使用的 `access_token` 不一致。
4. 无物理文件清理机制对应 OSS 删除；删除数据库记录后本地文件也可能残留（部分路由已处理本地删除，但不彻底）。
5. 移动端上传在 `admin.html` 中做了单独的单文件累加逻辑，与桌面端的拖拽批量上传是两套实现，维护时需注意同步。

---

## 变更日志规范 (Changelog)

项目根目录下的 `CHANGELOG.md` 用于记录每次迭代的变更内容，描述不超过30 字 

### 记录要求

- **每次功能迭代后必须更新**，包括新增功能、调整优化、Bug 修复
- **日期格式**：`YYYY-MM-DD`
- **内容分级**：
  - `### ✨ 新功能` — 新增模块、页面、接口、模型等
  - `### 🔧 调整与优化` — 现有功能的改进、重构、性能优化
  - `### 🐛 Bug 修复` — 问题修复
  - `### 🚀 项目启动` — 初始版本或重大里程碑

### 记录示例

```markdown
## 2026-05-18

### ✨ 新功能
- 新增 OpenClaw MCP Server，支持 9 个 Tools 调用
- 新增 `OpenClawToken` / `StudyPlan` 模型
- 新增 `backend/routes/openclaw.py`，提供 12+ 个专用 API 接口
- 新增 `frontend/settings.html` 个人设置页面

### 🔧 调整与优化
- OpenClaw 认证从双 Header（User-ID + Token）简化为单 Token 认证
- Token 支持有效期（1/3/6 个月）和 9 项细粒度权限控制

### 🐛 Bug 修复
- 修复 `.env` Docker 路径导致 Windows 本地 SQLite 无法打开的问题
- 修复配置指南链接 404 问题
```

### 注意事项

- 简单说明即可，无需罗列每一行代码变更
- 涉及模型/接口变更时，需注明新增或修改的文件路径
- 多人协作时，每次提交前检查并补充自己的变更记录

---

*本文档基于项目实际文件内容生成。修改项目结构、依赖或部署方式后，请及时更新本文件。*
