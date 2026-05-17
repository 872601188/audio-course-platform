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
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='student')  # admin / student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联关系
    progress_records = db.relationship('PlaybackProgress', backref='user', lazy=True,
                                        cascade='all, delete-orphan')
    courses_created = db.relationship('Course', backref='creator', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
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
