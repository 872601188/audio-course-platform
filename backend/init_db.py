#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
- 创建数据库表（如果不存在）
- 创建默认管理员账号
- 创建示例课程和测试音频

使用方法:
    cd backend
    python init_db.py
"""

import sys
import os

# 确保能导入 backend 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, User, Course, AudioFile
from werkzeug.security import generate_password_hash


def create_tables(app):
    """创建所有数据库表"""
    with app.app_context():
        db.create_all()
        print("✅ 数据库表创建成功")


def create_admin_user(app):
    """创建默认管理员账号"""
    with app.app_context():
        # 检查是否已存在管理员
        existing = User.query.filter_by(role='admin').first()
        if existing:
            print(f"⚠️ 管理员账号已存在: {existing.username}")
            return

        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ 管理员账号已创建")
        print("   用户名: admin")
        print("   密码: admin123")
        print("   ⚠️ 生产环境请务必修改密码！")


def create_demo_courses(app):
    """创建示例课程"""
    with app.app_context():
        # 检查是否已有课程
        if Course.query.first():
            print("⚠️ 已有课程数据，跳过示例创建")
            return

        admin = User.query.filter_by(role='admin').first()
        if not admin:
            print("❌ 未找到管理员用户，请先运行 create_admin_user")
            return

        courses_data = [
            {
                'title': 'Python 编程入门',
                'description': '从零开始学习 Python，涵盖基础语法、数据结构、函数和面向对象编程。适合完全零基础的学员。',
                'category': '编程',
                'cover_image': 'https://placehold.co/800x400/306998/ffffff?text=Python+Programming',
                'audios': [
                    {'title': '第1章：Python 简介与环境搭建', 'duration': 480, 'filename': 'demo_python_01.mp3'},
                    {'title': '第2章：变量与数据类型', 'duration': 600, 'filename': 'demo_python_02.mp3'},
                    {'title': '第3章：条件判断与循环', 'duration': 720, 'filename': 'demo_python_03.mp3'},
                ]
            },
            {
                'title': '英语口语实战',
                'description': '每天15分钟，提升英语口语能力。涵盖日常对话、商务场景、旅行用语。',
                'category': '英语',
                'cover_image': 'https://placehold.co/800x400/1D4ED8/ffffff?text=English+Speaking',
                'audios': [
                    {'title': 'Lesson 1：自我介绍', 'duration': 360, 'filename': 'demo_english_01.mp3'},
                    {'title': 'Lesson 2：点餐对话', 'duration': 420, 'filename': 'demo_english_02.mp3'},
                    {'title': 'Lesson 3：问路指引', 'duration': 390, 'filename': 'demo_english_03.mp3'},
                ]
            },
            {
                'title': '设计思维基础',
                'description': '学习设计思维方法论，掌握用户研究、原型设计和测试迭代的完整流程。',
                'category': '设计',
                'cover_image': 'https://placehold.co/800x400/E11D48/ffffff?text=Design+Thinking',
                'audios': [
                    {'title': '设计思维概述', 'duration': 540, 'filename': 'demo_design_01.mp3'},
                    {'title': '用户同理心地图', 'duration': 480, 'filename': 'demo_design_02.mp3'},
                    {'title': '快速原型制作', 'duration': 600, 'filename': 'demo_design_03.mp3'},
                ]
            }
        ]

        for course_data in courses_data:
            course = Course(
                title=course_data['title'],
                description=course_data['description'],
                category=course_data['category'],
                cover_image=course_data['cover_image'],
                created_by=admin.id
            )
            db.session.add(course)
            db.session.flush()  # 获取 course.id

            for idx, audio_data in enumerate(course_data['audios']):
                audio = AudioFile(
                    course_id=course.id,
                    title=audio_data['title'],
                    filename=audio_data['filename'],
                    original_name=audio_data['filename'],
                    duration=audio_data['duration'],
                    file_path=f"/uploads/audio/{audio_data['filename']}",
                    storage_type='local',
                    order_index=idx
                )
                db.session.add(audio)

        db.session.commit()
        print(f"✅ 已创建 {len(courses_data)} 门示例课程")


def create_student_user(app):
    """创建示例学员账号"""
    with app.app_context():
        existing = User.query.filter_by(username='student').first()
        if existing:
            print(f"⚠️ 学员账号已存在: {existing.username}")
            return

        student = User(
            username='student',
            email='student@example.com',
            password_hash=generate_password_hash('student123'),
            role='student'
        )
        db.session.add(student)
        db.session.commit()
        print("✅ 学员账号已创建")
        print("   用户名: student")
        print("   密码: student123")


def main():
    """主入口"""
    print("🚀 开始初始化数据库...")
    print("-" * 40)

    app = create_app()

    # 1. 创建表
    create_tables(app)

    # 2. 创建管理员
    create_admin_user(app)

    # 3. 创建学员
    create_student_user(app)

    # 4. 创建示例课程
    create_demo_courses(app)

    print("-" * 40)
    print("✅ 初始化完成！")
    print()
    print("📋 默认账号：")
    print("   管理员: admin / admin123")
    print("   学员: student / student123")
    print()
    print("🌐 访问 http://localhost:5000 开始使用")


if __name__ == '__main__':
    main()
