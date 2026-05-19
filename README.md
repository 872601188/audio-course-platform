# 🎧 习听云FM (Audio Course Platform)

基于 Flask + SQLite + TailwindCSS 的音频课程学习平台，支持批量上传、断点续播、学习分析等功能。

## ✨ 核心功能

1. **批量上传音频** - 拖拽上传多文件，支持 MP3/WAV/OGG/M4A/FLAC/AAC
2. **用户系统** - JWT 认证，管理员/学员角色
3. **课程管理** - 创建课程、关联音频、分类管理
4. **断点续播** - 自动保存播放进度，下次自动恢复
5. **学习分析** - 统计学习数据，提供个性化建议
6. **响应式前端** - 适配桌面端和移动端

## 🚀 快速开始

### 方式一：Docker（推荐）

```bash
# 1. 克隆项目
cd audio-course-platform

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 JWT_SECRET_KEY

# 3. 启动服务
docker-compose up -d

# 4. 初始化数据（创建管理员和示例课程）
docker-compose exec web python backend/init_db.py

# 5. 访问 http://localhost:5000
```

### 方式二：本地运行

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 2. 安装依赖
cd backend
pip install -r requirements.txt

# 3. 启动服务
cd backend
python app.py

# 4. 初始化数据（另一个终端）
python init_db.py

# 5. 访问 http://localhost:5000
```

## 📁 项目结构

```
audio-course-platform/
├── backend/
│   ├── app.py                  # Flask 主应用
│   ├── models.py               # 数据库模型（SQLite）
│   ├── init_db.py              # 初始化脚本
│   ├── requirements.txt        # Python 依赖
│   ├── instance/               # SQLite 数据库目录
│   ├── uploads/                # 文件上传目录
│   │   ├── audio/              # 音频文件
│   │   └── covers/             # 封面图片
│   ├── routes/
│   │   ├── auth.py             # 登录/注册
│   │   ├── courses.py          # 课程 CRUD
│   │   ├── upload.py           # 批量上传
│   │   ├── player.py           # 播放进度
│   │   └── analyze.py          # 学习分析
│   └── services/
│       └── openclaw_bridge.py  # AI 分析桥接
├── frontend/                   # 前端页面
│   ├── index.html              # 课程列表
│   ├── player.html             # 播放器
│   ├── admin.html              # 管理后台
│   ├── analyze.html            # 学习分析
│   ├── login.html              # 登录/注册
│   ├── css/
│   └── js/
│       ├── api.js              # API 封装
│       ├── auth.js             # 认证管理
│       ├── app.js              # 课程列表逻辑
│       └── player.js           # 播放器逻辑
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🔧 技术栈

- **后端**: Python Flask + SQLAlchemy + SQLite
- **前端**: HTML5 + TailwindCSS + Vanilla JS
- **认证**: Flask-JWT-Extended (Bearer Token)
- **音频**: HTML5 Audio API + 自定义控制
- **容器**: Docker + Docker Compose

## 📝 API 文档

### 认证
- `POST /api/register` - 注册
- `POST /api/login` - 登录（支持用户名或邮箱）
- `GET /api/me` - 当前用户信息

### 课程
- `GET /api/courses` - 课程列表（支持 category/search 参数）
- `GET /api/courses/:id` - 课程详情（含音频进度）
- `POST /api/courses` - 创建课程（管理员）
- `PUT /api/courses/:id` - 更新课程（管理员）
- `DELETE /api/courses/:id` - 删除课程（管理员）
- `POST /api/courses/:id/reorder` - 音频排序

### 上传
- `POST /api/upload/audio` - 批量上传音频（multipart/form-data）
- `POST /api/upload/cover` - 上传封面图片

### 播放器
- `GET /api/progress/:audio_id` - 获取播放进度
- `POST /api/progress/:audio_id` - 更新播放进度
- `POST /api/progress` - 记录学习行为日志
- `GET /api/progress/all` - 获取所有课程进度
- `GET /api/audio/:audio_id/stream` - 音频流

### 分析
- `POST /api/analyze-plan` - AI 学习分析
- `GET /api/learning-stats` - 学习统计

## 🧪 测试步骤

1. **启动服务**
   ```bash
   docker-compose up -d
   ```

2. **注册用户**
   - 访问 `http://localhost:5000`
   - 点击登录页面的"立即注册"
   - 注册管理员账号（role=admin）

3. **创建课程**
   - 登录后进入管理后台 `/admin.html`
   - 点击"新建课程"创建示例课程
   - 上传封面图片

4. **上传音频**
   - 在管理后台选择课程
   - 拖拽或选择音频文件批量上传
   - 为每个音频填写标题（可选）

5. **播放测试**
   - 回到首页，点击课程卡片
   - 进入播放器页面
   - 播放音频，拖动进度条
   - 刷新页面，验证断点续播

6. **学习分析**
   - 访问 `/analyze.html`
   - 查看学习统计和建议

## 🔐 安全注意事项

- 生产环境务必更换 `JWT_SECRET_KEY`
- 默认 SQLite 数据库文件在 `backend/instance/audio_course.db`
- 上传文件大小限制 500MB
- 所有管理员接口需 Bearer Token 认证

## 🐛 已知限制 / 待优化

1. 音频流未做范围请求支持（Range Request）
2. 学习分析目前使用本地启发式规则，AI 联动为预留接口
3. 移动端播放器界面可进一步优化
4. 缺少单元测试覆盖
5. 文件删除后数据库记录与物理文件可能不一致（需清理任务）
6. OSS 上传未做分片上传（大文件可能超时）

## 📄 License

MIT
