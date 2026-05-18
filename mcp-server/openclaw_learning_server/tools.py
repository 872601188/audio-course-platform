"""
MCP Tool definitions for OpenClaw Learning Assistant
Each tool maps to a backend API endpoint via the LearningAPIClient.
"""
from typing import Any
from mcp.server.fastmcp import FastMCP
from .client import LearningAPIClient


def register_tools(mcp: FastMCP, client: LearningAPIClient):
    """注册所有 Tools 到 MCP Server"""

    @mcp.tool()
    def get_courses(category: str = '', search: str = '') -> dict:
        """
        获取音频课程列表，支持按分类筛选和搜索。
        返回课程列表及每门课程的学习进度。
        """
        return client.get_courses(category=category, search=search)

    @mcp.tool()
    def get_learning_progress() -> dict:
        """
        获取用户总体学习进度。
        包括总学习时长、完成音频数、课程参与数等。
        """
        return client.get_progress()

    @mcp.tool()
    def get_learning_history(days: int = 30) -> dict:
        """
        获取用户学习历史记录。
        Args:
            days: 查询最近多少天的记录，默认30天
        """
        return client.get_history(days=days)

    @mcp.tool()
    def get_learning_stats() -> dict:
        """
        获取用户学习统计数据。
        包含最近7天、30天和全部时间的统计。
        """
        return client.get_stats()

    @mcp.tool()
    def get_daily_reminder(reminder_type: str = 'daily') -> dict:
        """
        获取今日或本周的学习督促提醒。
        包含计划完成度、优先推荐课程、薄弱环节和鼓励语。
        Args:
            reminder_type: 'daily'(每日) 或 'weekly'(每周)
        """
        return client.get_reminder(reminder_type=reminder_type)

    @mcp.tool()
    def create_study_plan(
        plan_type: str = 'daily',
        target_date: str = '',
        target_minutes: int = 30,
        target_courses: list = None,
        focus_areas: list = None,
        note: str = ''
    ) -> dict:
        """
        为用户创建学习计划（每日或每周）。
        Args:
            plan_type: 'daily' 或 'weekly'
            target_date: 目标日期，格式 YYYY-MM-DD，留空为今天
            target_minutes: 目标学习时长（分钟）
            target_courses: 目标课程ID列表
            focus_areas: 重点领域列表
            note: 计划备注/建议
        """
        return client.create_plan(
            plan_type=plan_type,
            target_date=target_date,
            target_minutes=target_minutes,
            target_courses=target_courses or [],
            focus_areas=focus_areas or [],
            note=note
        )

    @mcp.tool()
    def get_study_plan(plan_type: str = 'daily', target_date: str = '') -> dict:
        """
        获取当前有效的学习计划。
        Args:
            plan_type: 'daily' 或 'weekly'
            target_date: 查询指定日期的计划，格式 YYYY-MM-DD
        """
        return client.get_plan(plan_type=plan_type, target_date=target_date)

    @mcp.tool()
    def update_study_plan(plan_id: int, status: str = '', target_minutes: int = 0, note: str = '') -> dict:
        """
        更新学习计划的状态或内容。
        Args:
            plan_id: 计划ID
            status: 新状态，如 'active', 'completed', 'skipped'
            target_minutes: 新的目标时长
            note: 新的备注
        """
        payload = {}
        if status:
            payload['status'] = status
        if target_minutes > 0:
            payload['target_minutes'] = target_minutes
        if note:
            payload['note'] = note
        return client.update_plan(plan_id, **payload)

    @mcp.tool()
    def update_learning_progress(
        audio_id: int,
        current_time: float = 0.0,
        completed: bool = False,
        duration_listened: float = 0.0
    ) -> dict:
        """
        更新某个音频的学习进度。
        Args:
            audio_id: 音频ID
            current_time: 当前播放位置（秒）
            completed: 是否已完成
            duration_listened: 本次实际收听时长（秒）
        """
        return client.update_progress(
            audio_id=audio_id,
            current_time=current_time,
            completed=completed,
            duration_listened=duration_listened
        )
