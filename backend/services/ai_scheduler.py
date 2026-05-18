"""
AI 学习计划生成服务
支持调用外部 LLM API（OpenAI 兼容格式）或本地规则引擎回退。
"""
import os
import json
import re
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

try:
    import requests
except ImportError:
    requests = None


def _get_env(key: str, default: str = '') -> str:
    return os.environ.get(key, default)


def _call_llm_api(prompt: str) -> Optional[str]:
    """调用 LLM API，返回生成的文本内容"""
    api_key = _get_env('AI_API_KEY', '').strip()
    base_url = _get_env('AI_API_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    model = _get_env('AI_MODEL', 'gpt-4o-mini')

    if not api_key or requests is None:
        return None

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': '你是专业的学习规划专家，擅长根据用户时间和课程信息生成结构化学习计划。'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.5,
                'max_tokens': 3000
            },
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception:
        return None


def _parse_schedule_from_text(text: str) -> Optional[List[Dict]]:
    """从 LLM 返回的文本中提取 JSON 数组"""
    if not text:
        return None

    # 尝试提取 markdown 代码块中的 JSON
    code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if code_block:
        text = code_block.group(1).strip()

    # 尝试找到 JSON 数组
    array_match = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', text)
    if array_match:
        text = array_match.group(1).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_ai_prompt(user, courses: List[Dict], goal: str, daily_minutes: int,
                     plan_days: int, history_summary: str) -> str:
    """构建给 LLM 的 Prompt"""

    courses_text = "\n".join([
        f"- 《{c['title']}》(ID:{c['id']})，分类：{c.get('category','未分类')}，"
        f"共 {c.get('audio_count',0)} 个音频，总时长 {c.get('total_minutes',0)} 分钟，"
        f"当前进度 {c.get('progress_percent',0)}%"
        for c in courses
    ])

    prompt = f"""你是学习规划专家。请根据以下信息生成结构化学习计划。

## 用户信息
- 学习目标：{goal or '系统学习选定课程'}
- 每日可用时间：{daily_minutes} 分钟
- 计划周期：{plan_days} 天

## 课程列表
{courses_text}

## 学习历史摘要
{history_summary or '暂无学习历史'}

## 要求
1. 每天的学习时段合理分配，每个时段 20-45 分钟，中间有休息
2. 优先安排进度高但未完成的课程（冲刺完成）
3. 根据遗忘曲线安排复习（间隔 1/3/7 天）
4. 每天的总量不超过 {daily_minutes} 分钟
5. 返回严格的 JSON 数组格式，每个元素代表一天：

```json
[
  {{
    "day": 1,
    "date": "YYYY-MM-DD",
    "slots": [
      {{
        "start_time": "09:00",
        "end_time": "09:30",
        "course_id": 1,
        "course_title": "课程名",
        "audio_id": 1,
        "audio_title": "音频名",
        "expected_minutes": 30,
        "type": "new"
      }}
    ],
    "day_expected_minutes": 30
  }}
]
```

- `type` 只能是 `"new"`（新课）或 `"review"`（复习）
- `date` 从今天开始往后推算
- 只返回 JSON，不要其他说明文字
"""
    return prompt


def _generate_fallback_schedule(courses: List[Dict], daily_minutes: int,
                                plan_days: int, start_date: date) -> List[Dict]:
    """本地规则引擎：无 API Key 时的回退方案"""
    schedule = []

    # 收集所有音频，按课程分组
    all_audios = []
    for course in courses:
        audios = course.get('audio_files', course.get('audios', []))
        for idx, audio in enumerate(audios):
            all_audios.append({
                'course_id': course['id'],
                'course_title': course['title'],
                'audio_id': audio.get('id', idx + 1),
                'audio_title': audio.get('title', f'音频{idx + 1}'),
                'duration': audio.get('duration', 0),
                'progress_percent': course.get('progress_percent', 0),
                'type': 'new'
            })

    # 按进度降序排列（优先完成进度高的）
    all_audios.sort(key=lambda x: x['progress_percent'], reverse=True)

    audio_idx = 0
    total_audios = len(all_audios)

    for day in range(1, plan_days + 1):
        day_date = start_date + timedelta(days=day - 1)
        slots = []
        day_minutes = 0
        slot_start = 9 * 60  # 09:00 in minutes

        while day_minutes < daily_minutes and audio_idx < total_audios:
            audio = all_audios[audio_idx]
            expected = max(20, min(45, int(audio['duration'] / 60)))
            if expected <= 0:
                expected = 30
            if day_minutes + expected > daily_minutes:
                break

            start_h = slot_start // 60
            start_m = slot_start % 60
            end_h = (slot_start + expected) // 60
            end_m = (slot_start + expected) % 60

            slots.append({
                'start_time': f"{start_h:02d}:{start_m:02d}",
                'end_time': f"{end_h:02d}:{end_m:02d}",
                'course_id': audio['course_id'],
                'course_title': audio['course_title'],
                'audio_id': audio['audio_id'],
                'audio_title': audio['audio_title'],
                'expected_minutes': expected,
                'type': audio['type']
            })

            day_minutes += expected
            slot_start += expected + 10  # 休息 10 分钟
            audio_idx += 1

        if slots:
            schedule.append({
                'day': day,
                'date': day_date.isoformat(),
                'slots': slots,
                'day_expected_minutes': day_minutes
            })

    return schedule


def generate_study_plan(user, courses: List[Dict], goal: str, daily_minutes: int,
                        plan_days: int, history_summary: str = '') -> Dict:
    """
    生成学习计划
    优先使用 LLM API，失败则回退到本地规则引擎

    返回: {
        'ai_generated': bool,
        'schedule': List[Dict],
        'total_expected_minutes': int,
        'source': 'ai' | 'fallback'
    }
    """
    start_date = date.today()

    # 尝试 AI 生成
    prompt = _build_ai_prompt(user, courses, goal, daily_minutes, plan_days, history_summary)
    ai_text = _call_llm_api(prompt)
    ai_schedule = _parse_schedule_from_text(ai_text) if ai_text else None

    if ai_schedule and isinstance(ai_schedule, list) and len(ai_schedule) > 0:
        # 验证并补充 schedule
        for day_item in ai_schedule:
            for slot in day_item.get('slots', []):
                if 'audio_title' not in slot:
                    slot['audio_title'] = '未知音频'
                if 'course_title' not in slot:
                    slot['course_title'] = '未知课程'
                if 'type' not in slot:
                    slot['type'] = 'new'

        total_minutes = sum(
            d.get('day_expected_minutes', sum(s['expected_minutes'] for s in d.get('slots', [])))
            for d in ai_schedule
        )
        return {
            'ai_generated': True,
            'schedule': ai_schedule,
            'total_expected_minutes': total_minutes,
            'source': 'ai'
        }

    # 回退到本地规则引擎
    fallback_schedule = _generate_fallback_schedule(
        courses, daily_minutes, plan_days, start_date
    )
    total_minutes = sum(d['day_expected_minutes'] for d in fallback_schedule)

    return {
        'ai_generated': False,
        'schedule': fallback_schedule,
        'total_expected_minutes': total_minutes,
        'source': 'fallback'
    }


def create_executions_from_schedule(plan_id: int, user_id: int, schedule: List[Dict]):
    """根据 schedule 生成 PlanExecution 记录
    返回生成的 execution 对象列表（未 commit）
    """
    try:
        from backend.models import PlanExecution, db
    except ImportError:
        from models import PlanExecution, db

    executions = []
    for day_item in schedule:
        day_date = day_item.get('date')
        if isinstance(day_date, str):
            day_date = datetime.strptime(day_date, '%Y-%m-%d').date()

        for slot in day_item.get('slots', []):
            execution = PlanExecution(
                plan_id=plan_id,
                user_id=user_id,
                scheduled_date=day_date,
                scheduled_time=slot.get('start_time'),
                course_id=slot.get('course_id'),
                audio_id=slot.get('audio_id'),
                expected_minutes=slot.get('expected_minutes', 30),
                status='pending'
            )
            db.session.add(execution)
            executions.append(execution)

    return executions
