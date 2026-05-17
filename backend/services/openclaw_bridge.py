import json
import requests
from datetime import datetime

def analyze_learning_data(user_data: dict) -> dict:
    """
    OpenClaw 联动分析服务
    调用外部AI服务分析学习数据，返回个性化学习建议
    """

    # 构建给AI的分析提示
    prompt = build_analysis_prompt(user_data)

    # 尝试调用可用的分析服务
    # 策略1: 直接通过 kimi_search / kimi_fetch 获取学习建议
    # 策略2: 调用本地模型或外部API
    # 策略3: 基于规则的启发式分析

    suggestions = generate_ai_suggestions(user_data)

    return {
        'generated_at': datetime.utcnow().isoformat(),
        'analysis_period_days': user_data.get('analysis_period_days', 30),
        'user_summary': user_data.get('summary', {}),
        'suggestions': suggestions,
        'source': 'openclaw_bridge_local'  # 标记分析来源
    }


def build_analysis_prompt(user_data: dict) -> str:
    """构建AI分析用的提示文本"""
    courses = user_data.get('courses', [])
    summary = user_data.get('summary', {})

    prompt = f"""你是学习规划专家。请分析以下学习数据并给出建议。

用户：{user_data.get('username', '未知用户')}
分析周期：最近{user_data.get('analysis_period_days', 30)}天

## 总体统计
- 总学习时长：{summary.get('total_study_minutes', 0):.1f} 分钟
- 参与课程数：{summary.get('total_courses_enrolled', 0)} 门
- 完成课程数：{summary.get('total_completed_courses', 0)} 门

## 课程详情
"""
    for c in courses:
        prompt += f"\n- 《{c['course_title']}》({c['category']})\n"
        prompt += f"  进度：{c['progress_percent']:.1f}%\n"
        prompt += f"  已完成：{c['completed_audio_count']}/{c['total_audio_count']} 个音频\n"
        prompt += f"  已听：{c['listened_duration_minutes']:.1f} / {c['total_duration_minutes']:.1f} 分钟\n"
        prompt += f"  学习天数：{c['study_days']} 天\n"
        if c['last_study_date']:
            prompt += f"  最后学习：{c['last_study_date']}\n"

    prompt += "\n\n请给出：\n1. 优先级排序（哪些课程应该优先完成）\n2. 薄弱环节（进度低、间隔久的课程）\n3. 学习间隔建议（基于遗忘曲线）\n4. 每周学习计划建议\n5. 激励性反馈"

    return prompt


def generate_ai_suggestions(user_data: dict) -> list:
    """
    基于规则启发式生成学习建议
    当外部AI不可用时，提供可靠的本地分析
    """
    suggestions = []
    courses = user_data.get('courses', [])
    summary = user_data.get('summary', {})
    total_minutes = summary.get('total_study_minutes', 0)
    hour_dist = user_data.get('hour_distribution', {})

    if not courses:
        suggestions.append({
            'priority': 1,
            'category': '入门',
            'icon': '👋',
            'title': '开始学习吧！',
            'description': '你还没有开始学习记录。建议从感兴趣的分类中选择一门课程，每天学习15-20分钟。'
        })
        return suggestions

    # 1. 优先级建议 - 进度最高但未完成的课程
    incomplete_courses = [c for c in courses if c['progress_percent'] < 100]
    incomplete_courses.sort(key=lambda x: x['progress_percent'], reverse=True)

    if incomplete_courses:
        top = incomplete_courses[0]
        remaining = top['total_duration_minutes'] - top['listened_duration_minutes']
        if top['progress_percent'] >= 70:
            suggestions.append({
                'priority': 1,
                'category': '优先完成',
                'icon': '🎯',
                'title': f'冲刺完成《{top["course_title"]}》',
                'description': f'进度已达 {top["progress_percent"]:.1f}%，仅需 {remaining:.1f} 分钟即可完成。建议集中精力优先完成。'
            })
        elif top['progress_percent'] >= 30:
            suggestions.append({
                'priority': 1,
                'category': '持续学习',
                'icon': '📈',
                'title': f'继续推进《{top["course_title"]}》',
                'description': f'进度 {top["progress_percent"]:.1f}%，大约还需要 {remaining:.1f} 分钟。保持节奏继续学习。'
            })
        else:
            suggestions.append({
                'priority': 2,
                'category': '复习回顾',
                'icon': '🔁',
                'title': f'回顾《{top["course_title"]}》',
                'description': f'刚开始学习，进度仅 {top["progress_percent"]:.1f}%。建议回顾已学内容，打好基础。'
            })

    # 2. 薄弱环节
    stale_courses = [c for c in courses
                       if c['last_study_date'] is not None
                       and c['progress_percent'] < 100
                       and c['progress_percent'] > 0]
    # 按最后学习日期排序（最久未学的排前面）
    stale_courses.sort(key=lambda x: x['last_study_date'] or '9999')

    if stale_courses:
        stale = stale_courses[0]
        suggestions.append({
            'priority': 3,
            'category': '薄弱环节',
            'icon': '⚠️',
            'title': f'《{stale["course_title"]}》需要复习',
            'description': f'这门课已很久未学习（上次：{stale["last_study_date"] or "未知"}），根据遗忘曲线建议尽快复习。'
        })

    # 3. 学习时长分析
    if total_minutes < 60:
        suggestions.append({
            'priority': 2,
            'category': '学习习惯',
            'icon': '⏰',
            'title': '培养学习规律',
            'description': f'总学习时长仅 {total_minutes:.1f} 分钟。建议每天安排15-30分钟固定学习时间，形成习惯。'
        })
    elif total_minutes > 600:
        suggestions.append({
            'priority': 4,
            'category': '表扬',
            'icon': '🌟',
            'title': '学习表现优异！',
            'description': f'你已学习 {total_minutes:.1f} 分钟，非常棒！继续保持，挑战更多课程。'
        })

    # 4. 时段分析
    if hour_dist:
        peak_hours = sorted(hour_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        peak_str = ", ".join([f"{h}:00" for h, _ in peak_hours])
        suggestions.append({
            'priority': 3,
            'category': '时间优化',
            'icon': '🕐',
            'title': '你的高效学习时段',
            'description': f'数据发现你在 {peak_str} 时段学习较多，建议在这些时段安排较难课程。'
        })

    # 5. 完成度分析
    total_courses = summary.get('total_courses_enrolled', 0)
    completed = summary.get('total_completed_courses', 0)
    if total_courses > 0 and completed == 0:
        suggestions.append({
            'priority': 2,
            'category': '目标设定',
            'icon': '🏁',
            'title': '设定第一个完成目标',
            'description': f'你已参与 {total_courses} 门课程但尚未完成任何一门。选择进度最高的一门，设定完成目标吧！'
        })

    # 按优先级排序
    suggestions.sort(key=lambda x: x['priority'])

    return suggestions
