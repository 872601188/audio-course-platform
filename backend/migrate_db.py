#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本 - 用于生产环境添加新表和新列
由于服务器使用 SQLite，db.create_all() 不会修改已有表结构，
此脚本使用 sqlite3 直接执行 ALTER TABLE。
"""
import os
import sys
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'audio_course.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 确保 plan_executions 表存在（新表通常由 db.create_all() 创建）
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plan_executions'")
    if not cursor.fetchone():
        print("创建 plan_executions 表...")
        cursor.execute('''
            CREATE TABLE plan_executions (
                id INTEGER PRIMARY KEY,
                plan_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                scheduled_date DATE NOT NULL,
                scheduled_time VARCHAR(10),
                course_id INTEGER,
                audio_id INTEGER,
                expected_minutes INTEGER DEFAULT 0,
                actual_minutes FLOAT DEFAULT 0.0,
                status VARCHAR(20) DEFAULT 'pending',
                completed_at DATETIME,
                note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        print("plan_executions 表已存在")

    # 2. 为 study_plans 表添加新列（如果缺失）
    cursor.execute('PRAGMA table_info(study_plans)')
    existing_cols = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ('ai_generated', 'BOOLEAN DEFAULT 0'),
        ('schedule', 'TEXT'),
        ('total_expected_minutes', 'INTEGER DEFAULT 0'),
        ('learning_goal', 'TEXT'),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            print(f"为 study_plans 添加列: {col_name}")
            cursor.execute(f'ALTER TABLE study_plans ADD COLUMN {col_name} {col_type}')
        else:
            print(f"列已存在: {col_name}")

    # 3. 为 openclaw_tokens 表添加 token_key 列
    cursor.execute('PRAGMA table_info(openclaw_tokens)')
    existing_oc_cols = {row[1] for row in cursor.fetchall()}
    if 'token_key' not in existing_oc_cols:
        print("为 openclaw_tokens 添加列: token_key")
        cursor.execute("ALTER TABLE openclaw_tokens ADD COLUMN token_key VARCHAR(100)")
    else:
        print("列已存在: token_key")

    conn.commit()
    conn.close()
    print("✅ 数据库迁移完成")


if __name__ == '__main__':
    migrate()
