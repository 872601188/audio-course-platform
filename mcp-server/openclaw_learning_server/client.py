"""
HTTP Client for Audio Course Platform API
Handles authentication and API calls to the Flask backend.
"""
import os
import httpx
from typing import Any, Optional


class LearningAPIClient:
    """学习平台 API 客户端
    认证方式：仅通过 X-OpenClaw-Token，Token 本身即绑定用户身份。
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = (base_url or os.environ.get('LEARNING_API_URL', 'http://localhost:5000')).rstrip('/')
        self.token = token or os.environ.get('LEARNING_API_TOKEN', '')
        self.client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict:
        return {
            'X-OpenClaw-Token': self.token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/openclaw{path}"

    def get_courses(self, category: str = '', search: str = '') -> dict:
        """获取课程列表"""
        params = {}
        if category:
            params['category'] = category
        if search:
            params['search'] = search
        resp = self.client.get(self._url('/courses'), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_progress(self) -> dict:
        """获取学习进度"""
        resp = self.client.get(self._url('/progress'), headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_history(self, days: int = 30) -> dict:
        """获取学习历史"""
        resp = self.client.get(self._url('/history'), headers=self._headers(), params={'days': days})
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> dict:
        """获取学习统计"""
        resp = self.client.get(self._url('/stats'), headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_reminder(self, reminder_type: str = 'daily') -> dict:
        """获取学习督促提醒"""
        resp = self.client.get(self._url('/reminder'), headers=self._headers(), params={'type': reminder_type})
        resp.raise_for_status()
        return resp.json()

    def create_plan(self, plan_type: str = 'daily', target_date: str = '', target_minutes: int = 30,
                    target_courses: Optional[list] = None, focus_areas: Optional[list] = None,
                    note: str = '') -> dict:
        """创建学习计划"""
        payload = {
            'plan_type': plan_type,
            'target_minutes': target_minutes,
            'target_courses': target_courses or [],
            'focus_areas': focus_areas or [],
            'note': note
        }
        if target_date:
            payload['target_date'] = target_date
        resp = self.client.post(self._url('/plan'), headers=self._headers(), json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_plan(self, plan_type: str = 'daily', target_date: str = '') -> dict:
        """获取学习计划"""
        params = {'type': plan_type}
        if target_date:
            params['date'] = target_date
        resp = self.client.get(self._url('/plan'), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def update_plan(self, plan_id: int, **kwargs) -> dict:
        """更新学习计划"""
        resp = self.client.put(self._url(f'/plan/{plan_id}'), headers=self._headers(), json=kwargs)
        resp.raise_for_status()
        return resp.json()

    def update_progress(self, audio_id: int, current_time: float = 0.0, completed: bool = False,
                        duration_listened: float = 0.0) -> dict:
        """更新学习进度"""
        payload = {
            'audio_id': audio_id,
            'current_time': current_time,
            'completed': completed,
            'duration_listened': duration_listened
        }
        resp = self.client.post(self._url('/progress'), headers=self._headers(), json=payload)
        resp.raise_for_status()
        return resp.json()

    def ai_generate_plan(self, learning_goal: str = '', daily_available_minutes: int = 60,
                         plan_days: int = 7, target_courses: Optional[list] = None,
                         focus_areas: Optional[list] = None) -> dict:
        """AI 生成学习计划"""
        payload = {
            'learning_goal': learning_goal,
            'daily_available_minutes': daily_available_minutes,
            'plan_days': plan_days,
            'target_courses': target_courses or [],
            'focus_areas': focus_areas or []
        }
        resp = self.client.post(self._url('/plan/ai-generate'), headers=self._headers(), json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_plan_execution(self, plan_id: int = 0, exec_date: str = '', status: str = '') -> dict:
        """获取计划执行列表"""
        params = {}
        if plan_id:
            params['plan_id'] = plan_id
        if exec_date:
            params['date'] = exec_date
        if status:
            params['status'] = status
        resp = self.client.get(self._url('/plan/execution'), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_plan_progress(self, plan_id: int = 0) -> dict:
        """获取计划总体完成进度"""
        params = {}
        if plan_id:
            params['plan_id'] = plan_id
        resp = self.client.get(self._url('/plan/progress'), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def sync_plan_execution(self, plan_id: int = 0) -> dict:
        """自动同步计划执行状态"""
        params = {}
        if plan_id:
            params['plan_id'] = plan_id
        resp = self.client.post(self._url('/plan/sync'), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self.client.close()
