from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

try:
    from backend.models import db, User, AudioFile, Course, PlaybackProgress, StudyLog
except ImportError:
    from models import db, User, AudioFile, Course, PlaybackProgress, StudyLog

try:
    from backend.services.openclaw_bridge import analyze_learning_data
except ImportError:
    from services.openclaw_bridge import analyze_learning_data

analyze_bp = Blueprint('analyze', __name__)


@analyze_bp.route('/analyze-plan', methods=['POST'])
@jwt_required()
def analyze_plan():
    """
    OpenClaw 联动分析接口
    接收用户学习数据，调用 AI 分析学习模式，返回个性化建议
    """
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json() or {}
    days = data.get('days', 30)  # 分析最近多少天的数据

    # 1. 收集用户学习数据
    since = datetime.utcnow() - timedelta(days=days)

    # 播放记录
    progress_records = PlaybackProgress.query.filter(
        PlaybackProgress.user_id == user.id,
        PlaybackProgress.last_played_at >= since
    ).all()

    # 学习日志
    study_logs = StudyLog.query.filter(
        StudyLog.user_id == user.id,
        StudyLog.created_at >= since
    ).order_by(StudyLog.created_at.desc()).all()

    # 2. 构建分析数据
    courses_data = []
    course_ids = set()

    for p in progress_records:
        audio = AudioFile.query.get(p.audio_id)
        if not audio:
            continue
        course_ids.add(audio.course_id)

    for course_id in course_ids:
        course = Course.query.get(course_id)
        if not course:
            continue

        course_audios = AudioFile.query.filter_by(course_id=course_id).all()
        total_duration = sum(a.duration for a in course_audios)

        # 该用户在该课程的进度
        listened_duration = 0
        completed_count = 0
        for audio in course_audios:
            prog = PlaybackProgress.query.filter_by(
                user_id=user.id, audio_id=audio.id
            ).first()
            if prog:
                listened_duration += min(prog.current_time, audio.duration)
                if prog.completed:
                    completed_count += 1

        # 学习频率统计
        course_logs = [l for l in study_logs if l.course_id == course_id]
        study_dates = set()
        for log in course_logs:
            study_dates.add(log.created_at.strftime('%Y-%m-%d'))

        courses_data.append({
            'course_id': course_id,
            'course_title': course.title,
            'category': course.category,
            'total_audio_count': len(course_audios),
            'completed_audio_count': completed_count,
            'progress_percent': round(listened_duration / total_duration * 100, 1) if total_duration > 0 else 0,
            'total_duration_minutes': round(total_duration / 60, 1),
            'listened_duration_minutes': round(listened_duration / 60, 1),
            'study_days': len(study_dates),
            'last_study_date': max(study_dates) if study_dates else None
        })

    # 学习时段分布
    hour_distribution = {}
    for log in study_logs:
        hour = log.created_at.hour
        hour_distribution[hour] = hour_distribution.get(hour, 0) + log.duration_listened

    # 总体统计
    total_study_minutes = round(sum(c['listened_duration_minutes'] for c in courses_data), 1)
    total_completed_courses = sum(1 for c in courses_data if c['progress_percent'] >= 100)

    analysis_data = {
        'user_id': user.id,
        'username': user.username,
        'analysis_period_days': days,
        'analysis_date': datetime.utcnow().isoformat(),
        'summary': {
            'total_study_minutes': total_study_minutes,
            'total_courses_enrolled': len(courses_data),
            'total_completed_courses': total_completed_courses,
            'total_study_logs': len(study_logs)
        },
        'courses': courses_data,
        'hour_distribution': hour_distribution,
        'raw_logs': [
            {
                'course_id': l.course_id,
                'audio_id': l.audio_id,
                'action': l.action,
                'position': l.position,
                'duration_listened': l.duration_listened,
                'created_at': l.created_at.isoformat()
            }
            for l in study_logs[:50]  # 只取最近50条，避免数据过大
        ]
    }

    # 3. 调用 OpenClaw 分析
    try:
        analysis_result = analyze_learning_data(analysis_data)
        return jsonify({
            'success': True,
            'analysis': analysis_result,
            'data_summary': analysis_data['summary']
        }), 200
    except Exception as e:
        # 如果AI分析失败，返回基础统计
        return jsonify({
            'success': True,
            'analysis': {
                'error': f'AI分析暂时不可用: {str(e)}',
                'fallback_suggestions': generate_fallback_suggestions(courses_data, total_study_minutes)
            },
            'data_summary': analysis_data['summary']
        }), 200


def generate_fallback_suggestions(courses_data, total_study_minutes):
    """AI分析失败时的回退建议"""
    suggestions = []

    # 按进度排序，找出需要优先完成的课程
    incomplete = [c for c in courses_data if c['progress_percent'] < 100]
    incomplete.sort(key=lambda x: x['progress_percent'], reverse=True)

    if incomplete:
        top_course = incomplete[0]
        suggestions.append({
            'type': 'priority',
            'priority': 1,
            'title': f'优先完成《{top_course["course_title"]}》',
            'description': f'进度 {top_course["progress_percent"]}%，只差 {round(top_course["total_duration_minutes"] - top_course["listened_duration_minutes"], 1)} 分钟，建议优先完成'
        })

    if total_study_minutes < 60:
        suggestions.append({
            'type': 'habit',
            'priority': 2,
            'title': '培养学习习惯',
            'description': '总学习时长不足1小时，建议每天固定学习15-30分钟'
        })

    # 找出进度较低的课程
    low_progress = [c for c in courses_data if 0 < c['progress_percent'] < 30]
    if low_progress:
        suggestions.append({
            'type': 'review',
            'priority': 3,
            'title': '回顾已开始的课程',
            'description': f'有 {len(low_progress)} 门课程进度低于30%，建议回顾巩固'
        })

    return suggestions


@analyze_bp.route('/learning-stats', methods=['GET'])
@jwt_required()
def get_learning_stats():
    """获取学习统计数据 - 用于仪表盘展示"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    # 最近7天和30天统计
    now = datetime.utcnow()
    stats = {
        'last_7_days': {},
        'last_30_days': {},
        'all_time': {}
    }

    for period_name, days in [('last_7_days', 7), ('last_30_days', 30), ('all_time', 365*10)]:
        since = now - timedelta(days=days)

        # 播放记录统计
        progress_records = PlaybackProgress.query.filter(
            PlaybackProgress.user_id == user.id,
            PlaybackProgress.last_played_at >= since
        ).all()

        # 学习日志统计
        study_logs = StudyLog.query.filter(
            StudyLog.user_id == user.id,
            StudyLog.created_at >= since
        ).all()

        total_listened = sum(
            min(p.current_time, AudioFile.query.get(p.audio_id).duration or 0)
            for p in progress_records
            if AudioFile.query.get(p.audio_id)
        )

        completed_count = sum(1 for p in progress_records if p.completed)
        unique_courses = set()
        unique_audios = set()
        for p in progress_records:
            unique_audios.add(p.audio_id)
            audio = AudioFile.query.get(p.audio_id)
            if audio:
                unique_courses.add(audio.course_id)

        # 时段分布
        hour_dist = {}
        for log in study_logs:
            h = log.created_at.hour
            hour_dist[h] = hour_dist.get(h, 0) + log.duration_listened

        # 每日分布
        daily_dist = {}
        for log in study_logs:
            d = log.created_at.strftime('%Y-%m-%d')
            daily_dist[d] = daily_dist.get(d, 0) + log.duration_listened

        stats[period_name] = {
            'total_study_minutes': round(total_listened / 60, 1),
            'completed_audio_count': completed_count,
            'total_audio_played': len(unique_audios),
            'total_courses_touched': len(unique_courses),
            'study_log_count': len(study_logs),
            'hour_distribution': {str(k): round(v/60, 1) for k, v in hour_dist.items()},
            'daily_distribution': {k: round(v/60, 1) for k, v in daily_dist.items()}
        }

    return jsonify({
        'stats': stats,
        'user': user.to_dict()
    }), 200
