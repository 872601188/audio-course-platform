"""
我的学习 - 个人学习进度与计划查询（JWT 认证）
为前端提供统一的学习数据聚合接口
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date
import json

try:
    from backend.models import (
        db, User, Course, AudioFile, PlaybackProgress, StudyLog,
        StudyPlan, PlanExecution
    )
except ImportError:
    from models import (
        db, User, Course, AudioFile, PlaybackProgress, StudyLog,
        StudyPlan, PlanExecution
    )

my_bp = Blueprint('my', __name__)


@my_bp.route('/my/progress', methods=['GET'])
@jwt_required()
def get_my_progress():
    """获取我的所有课程学习进度"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    courses = Course.query.order_by(Course.created_at.desc()).all()
    result = []

    for course in courses:
        audios = AudioFile.query.filter_by(course_id=course.id).order_by(AudioFile.order_index).all()
        if not audios:
            continue

        total_duration = sum(a.duration for a in audios)
        listened_duration = 0
        completed_count = 0
        last_study = None
        audio_progress = []

        for audio in audios:
            prog = PlaybackProgress.query.filter_by(user_id=user.id, audio_id=audio.id).first()
            audio_data = {
                'id': audio.id,
                'title': audio.title,
                'duration': audio.duration,
                'current_time': 0,
                'completed': False,
                'play_count': 0
            }
            if prog:
                listened = min(prog.current_time, audio.duration)
                listened_duration += listened
                audio_data['current_time'] = prog.current_time
                audio_data['completed'] = prog.completed
                audio_data['play_count'] = prog.play_count
                if prog.completed:
                    completed_count += 1
                if prog.last_played_at:
                    if last_study is None or prog.last_played_at > last_study:
                        last_study = prog.last_played_at

            audio_progress.append(audio_data)

        progress_percent = round(listened_duration / total_duration * 100, 1) if total_duration > 0 else 0

        result.append({
            'course_id': course.id,
            'course_title': course.title,
            'category': course.category,
            'cover_image': course.cover_image,
            'progress_percent': progress_percent,
            'completed_audio_count': completed_count,
            'total_audio_count': len(audios),
            'listened_minutes': round(listened_duration / 60, 1),
            'total_minutes': round(total_duration / 60, 1),
            'last_study_at': last_study.isoformat() if last_study else None,
            'audio_progress': audio_progress
        })

    # 按最后学习时间倒序排列
    result.sort(key=lambda x: x['last_study_at'] or '', reverse=True)

    # 汇总统计
    total_listened = sum(c['listened_minutes'] for c in result)
    total_completed = sum(c['completed_audio_count'] for c in result)
    total_audios = sum(c['total_audio_count'] for c in result)
    studied_courses = [c for c in result if c['listened_minutes'] > 0]

    return jsonify({
        'courses': result,
        'summary': {
            'total_courses': len(result),
            'studied_courses': len(studied_courses),
            'total_listened_minutes': round(total_listened, 1),
            'total_completed_audios': total_completed,
            'total_audios': total_audios
        }
    }), 200


@my_bp.route('/my/plans', methods=['GET'])
@jwt_required()
def get_my_plans():
    """获取我的学习计划列表"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    plans = StudyPlan.query.filter_by(user_id=user.id).order_by(StudyPlan.created_at.desc()).all()
    result = []

    for plan in plans:
        # 统计执行记录
        executions = PlanExecution.query.filter_by(plan_id=plan.id).all()
        total = len(executions)
        completed = sum(1 for e in executions if e.status == 'completed')
        total_expected = sum(e.expected_minutes for e in executions)
        total_actual = sum(e.actual_minutes for e in executions)

        # 今日任务
        today = date.today()
        today_executions = PlanExecution.query.filter_by(
            plan_id=plan.id, scheduled_date=today
        ).order_by(PlanExecution.scheduled_time).all()

        today_tasks = []
        for e in today_executions:
            course = Course.query.get(e.course_id) if e.course_id else None
            audio = AudioFile.query.get(e.audio_id) if e.audio_id else None
            today_tasks.append({
                'id': e.id,
                'scheduled_time': e.scheduled_time,
                'course_title': course.title if course else '未知课程',
                'audio_title': audio.title if audio else '未知音频',
                'expected_minutes': e.expected_minutes,
                'actual_minutes': round(e.actual_minutes, 1),
                'status': e.status
            })

        # 按日期聚合执行记录（用于热力图）
        date_status_map = {}
        for e in executions:
            d = e.scheduled_date.isoformat() if e.scheduled_date else None
            if not d:
                continue
            if d not in date_status_map:
                date_status_map[d] = []
            date_status_map[d].append(e.status)

        heatmap = []
        for d in sorted(date_status_map.keys()):
            statuses = date_status_map[d]
            if 'completed' in statuses:
                day_status = 'completed'
            elif 'in_progress' in statuses:
                day_status = 'planned'
            elif 'pending' in statuses:
                day_status = 'planned'
            else:
                day_status = 'skipped'
            heatmap.append({'date': d, 'status': day_status})

        result.append({
            'id': plan.id,
            'plan_type': plan.plan_type,
            'target_date': plan.target_date.isoformat() if plan.target_date else None,
            'target_minutes': plan.target_minutes,
            'status': plan.status,
            'note': plan.note,
            'ai_generated': plan.ai_generated,
            'learning_goal': plan.learning_goal,
            'total_expected_minutes': plan.total_expected_minutes,
            'created_at': plan.created_at.isoformat() if plan.created_at else None,
            'progress': {
                'total_slots': total,
                'completed_slots': completed,
                'completion_rate': round(completed / total * 100, 1) if total > 0 else 0,
                'total_expected_minutes': total_expected,
                'total_actual_minutes': round(total_actual, 1)
            },
            'today_tasks': today_tasks,
            'heatmap': heatmap
        })

    return jsonify({'plans': result}), 200


@my_bp.route('/my/plans/<int:plan_id>', methods=['GET'])
@jwt_required()
def get_my_plan_detail(plan_id):
    """获取单个学习计划详情（含执行记录）"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    plan = StudyPlan.query.filter_by(id=plan_id, user_id=user.id).first()
    if not plan:
        return jsonify({'error': '计划不存在'}), 404

    executions = PlanExecution.query.filter_by(plan_id=plan.id).order_by(
        PlanExecution.scheduled_date, PlanExecution.scheduled_time
    ).all()

    exec_list = []
    for e in executions:
        course = Course.query.get(e.course_id) if e.course_id else None
        audio = AudioFile.query.get(e.audio_id) if e.audio_id else None
        exec_list.append({
            'id': e.id,
            'scheduled_date': e.scheduled_date.isoformat() if e.scheduled_date else None,
            'scheduled_time': e.scheduled_time,
            'course': {
                'id': course.id if course else None,
                'title': course.title if course else '未知课程'
            },
            'audio': {
                'id': audio.id if audio else None,
                'title': audio.title if audio else '未知音频'
            },
            'expected_minutes': e.expected_minutes,
            'actual_minutes': round(e.actual_minutes, 1),
            'status': e.status,
            'completed_at': e.completed_at.isoformat() if e.completed_at else None,
            'note': e.note
        })

    total = len(exec_list)
    completed = sum(1 for e in exec_list if e['status'] == 'completed')

    return jsonify({
        'plan': plan.to_dict(),
        'executions': exec_list,
        'summary': {
            'total_slots': total,
            'completed_slots': completed,
            'completion_rate': round(completed / total * 100, 1) if total > 0 else 0
        }
    }), 200
