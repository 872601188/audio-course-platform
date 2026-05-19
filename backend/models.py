from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class User(db.Model):
    """用户模型 - 支持管理员和学员两种角色"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='student')  # admin / student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联关系
    progress_records = db.relationship('PlaybackProgress', backref='user', lazy=True,
                                        cascade='all, delete-orphan')
    courses_created = db.relationship('Course', backref='creator', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True,
                                 cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Course(db.Model):
    """课程模型 - 包含多个音频文件"""
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), default='未分类')
    cover_image = db.Column(db.String(500))  # 封面图路径或URL
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联关系
    audio_files = db.relationship('AudioFile', backref='course', lazy=True,
                                   order_by='AudioFile.order_index',
                                   cascade='all, delete-orphan')

    def to_dict(self, with_audios=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'cover_image': self.cover_image,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'audio_count': len(self.audio_files)
        }
        if with_audios:
            data['audio_files'] = [a.to_dict() for a in self.audio_files]
        return data


class AudioFile(db.Model):
    """音频文件模型 - 属于某个课程"""
    __tablename__ = 'audio_files'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(500), nullable=False)  # 存储后的文件名
    original_name = db.Column(db.String(500))  # 原始文件名
    duration = db.Column(db.Float, default=0.0)  # 时长（秒）
    file_path = db.Column(db.String(500), nullable=False)  # 本地路径或OSS URL
    storage_type = db.Column(db.String(20), default='local')  # local / oss
    order_index = db.Column(db.Integer, default=0)  # 排序
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联关系
    progress_records = db.relationship('PlaybackProgress', backref='audio', lazy=True,
                                        cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'filename': self.filename,
            'original_name': self.original_name,
            'duration': self.duration,
            'file_path': self.file_path,
            'storage_type': self.storage_type,
            'order_index': self.order_index,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class PlaybackProgress(db.Model):
    """播放进度模型 - 记录每个用户每个音频的播放位置"""
    __tablename__ = 'playback_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    audio_id = db.Column(db.Integer, db.ForeignKey('audio_files.id'), nullable=False)
    current_time = db.Column(db.Float, default=0.0)  # 当前播放位置（秒）
    completed = db.Column(db.Boolean, default=False)  # 是否已听完
    last_played_at = db.Column(db.DateTime, default=datetime.utcnow)
    play_count = db.Column(db.Integer, default=1)  # 播放次数

    # 唯一约束：每个用户对每个音频只有一条记录
    __table_args__ = (db.UniqueConstraint('user_id', 'audio_id', name='uix_user_audio'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'audio_id': self.audio_id,
            'current_time': self.current_time,
            'completed': self.completed,
            'last_played_at': self.last_played_at.isoformat() if self.last_played_at else None,
            'play_count': self.play_count
        }


class Favorite(db.Model):
    """用户收藏 - 收藏音频文件"""
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    audio_id = db.Column(db.Integer, db.ForeignKey('audio_files.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 唯一约束：每个用户每个音频只收藏一次
    __table_args__ = (db.UniqueConstraint('user_id', 'audio_id', name='uix_user_audio_fav'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'audio_id': self.audio_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class StudyLog(db.Model):
    """学习日志 - 用于分析学习模式"""
    __tablename__ = 'study_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    audio_id = db.Column(db.Integer, db.ForeignKey('audio_files.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    action = db.Column(db.String(50))  # play / pause / complete / seek
    position = db.Column(db.Float, default=0.0)
    duration_listened = db.Column(db.Float, default=0.0)  # 本次实际收听时长
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'audio_id': self.audio_id,
            'course_id': self.course_id,
            'action': self.action,
            'position': self.position,
            'duration_listened': self.duration_listened,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 默认权限集合：所有读取权限 + 计划写入权限
DEFAULT_OPENCLAW_PERMISSIONS = [
    'read:courses', 'read:progress', 'read:history', 'read:stats',
    'read:reminder', 'read:plan', 'write:plan', 'write:progress'
]

ALL_OPENCLAW_PERMISSIONS = [
    {'key': 'read:courses', 'label': '获取课程列表', 'category': '读取'},
    {'key': 'read:progress', 'label': '获取学习进度', 'category': '读取'},
    {'key': 'read:history', 'label': '获取学习历史', 'category': '读取'},
    {'key': 'read:stats', 'label': '获取学习统计', 'category': '读取'},
    {'key': 'read:reminder', 'label': '获取督促提醒', 'category': '读取'},
    {'key': 'read:plan', 'label': '获取学习计划', 'category': '读取'},
    {'key': 'write:plan', 'label': '创建/更新学习计划', 'category': '写入'},
    {'key': 'delete:plan', 'label': '删除学习计划', 'category': '删除'},
    {'key': 'write:progress', 'label': '更新学习进度', 'category': '写入'},
]


class OpenClawToken(db.Model):
    """OpenClaw API 访问令牌 - 每个用户可生成独立 Token
    支持有效期和细粒度权限控制。
    """
    __tablename__ = 'openclaw_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    token_key = db.Column(db.String(100))  # 可查看的明文 token，sk- 开头
    name = db.Column(db.String(100), default='OpenClaw')
    is_active = db.Column(db.Boolean, default=True)
    # 有效期：默认 3 个月（90 天）
    expires_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=90))
    # 权限：JSON 数组字符串，如 ["read:courses", "write:plan"]
    permissions = db.Column(db.Text, default=lambda: json.dumps(DEFAULT_OPENCLAW_PERMISSIONS))
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token_key': self.token_key,
            'name': self.name,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'permissions': json.loads(self.permissions) if self.permissions else [],
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def is_expired(self):
        """检查 Token 是否已过期"""
        return datetime.utcnow() > self.expires_at

    def has_permission(self, permission):
        """检查是否拥有指定权限"""
        perms = json.loads(self.permissions) if self.permissions else []
        return permission in perms


class StudyPlan(db.Model):
    """学习计划 - 用户每日/每周学习目标
    支持 AI 生成详细时间安排（schedule JSON）。
    """
    __tablename__ = 'study_plans'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)  # daily / weekly / custom
    target_date = db.Column(db.Date, nullable=False)
    target_minutes = db.Column(db.Integer, default=30)
    target_courses = db.Column(db.Text)  # JSON 数组
    focus_areas = db.Column(db.Text)  # JSON 数组
    status = db.Column(db.String(20), default='active')  # active / completed / skipped / replaced
    note = db.Column(db.Text)
    # AI 计划生成扩展字段
    ai_generated = db.Column(db.Boolean, default=False)
    schedule = db.Column(db.Text)  # JSON：详细时间安排（含时段、课程、音频）
    total_expected_minutes = db.Column(db.Integer, default=0)
    learning_goal = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_type': self.plan_type,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'target_minutes': self.target_minutes,
            'target_courses': json.loads(self.target_courses) if self.target_courses else [],
            'focus_areas': json.loads(self.focus_areas) if self.focus_areas else [],
            'status': self.status,
            'note': self.note,
            'ai_generated': self.ai_generated,
            'schedule': json.loads(self.schedule) if self.schedule else [],
            'total_expected_minutes': self.total_expected_minutes,
            'learning_goal': self.learning_goal,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class PlanExecution(db.Model):
    """计划执行跟踪 — 每个时段一条记录
    用于记录预期 vs 实际完成情况，供 OpenClaw 查询。
    """
    __tablename__ = 'plan_executions'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('study_plans.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.String(10))       # HH:MM
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    audio_id = db.Column(db.Integer, db.ForeignKey('audio_files.id'))
    expected_minutes = db.Column(db.Integer, default=0)
    actual_minutes = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending / in_progress / completed / skipped
    completed_at = db.Column(db.DateTime)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'user_id': self.user_id,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'scheduled_time': self.scheduled_time,
            'course_id': self.course_id,
            'audio_id': self.audio_id,
            'expected_minutes': self.expected_minutes,
            'actual_minutes': self.actual_minutes,
            'status': self.status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
