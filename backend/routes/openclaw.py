"""
OpenClaw 集成路由 - 为 MCP Server / CLI 提供专用 API
认证方式：Header X-OpenClaw-Token（Token 本身绑定用户，无需额外传 User-ID）
权限控制：每个 Token 可独立配置有效期和细粒度权限
"""
import hashlib
import secrets
import json
from datetime import datetime, timedelta, date
from functools import wraps

from flask import Blueprint, request, jsonify, g, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.models import (
    db, User, Course, AudioFile, PlaybackProgress, StudyLog,
    OpenClawToken, StudyPlan, ALL_OPENCLAW_PERMISSIONS, DEFAULT_OPENCLAW_PERMISSIONS
)

openclaw_bp = Blueprint('openclaw', __name__)


def openclaw_auth_required(f):
    """OpenClaw Token 认证装饰器
    仅通过 X-OpenClaw-Token 即可确定用户身份。
    同时检查 Token 是否过期，并将权限注入 g.current_permissions。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-OpenClaw-Token')

        if not token:
            return jsonify({'error': '缺少认证信息，需要在 Header 中提供 X-OpenClaw-Token'}), 401

        # 计算 Token 的 SHA256 hash
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # 通过 Token hash 查找记录（自动确定所属用户）
        token_record = OpenClawToken.query.filter_by(
            token_hash=token_hash,
            is_active=True
        ).first()

        if not token_record:
            return jsonify({'error': 'Token 无效或已撤销'}), 401

        # 检查是否过期
        if token_record.is_expired():
            return jsonify({'error': 'Token 已过期，请重新生成'}), 401

        # 可选：如果客户端也传了 X-User-ID，做一致性校验
        client_user_id = request.headers.get('X-User-ID')
        if client_user_id is not None:
            try:
                if int(client_user_id) != token_record.user_id:
                    return jsonify({'error': 'Token 与提供的 User-ID 不匹配'}), 401
            except ValueError:
                return jsonify({'error': 'X-User-ID 必须是整数'}), 401

        # 更新最后使用时间
        token_record.last_used_at = datetime.utcnow()
        db.session.commit()

        # 获取用户并注入 g
        user = User.query.get(token_record.user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 401

        g.current_user = user
        g.current_token = token_record
        g.current_permissions = json.loads(token_record.permissions) if token_record.permissions else []
        return f(*args, **kwargs)
    return decorated


def require_permission(permission):
    """权限检查装饰器工厂，用于在 openclaw_auth_required 之后检查特定权限"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            perms = getattr(g, 'current_permissions', [])
            if permission not in perms:
                return jsonify({
                    'error': f'权限不足，当前 Token 缺少权限: {permission}',
                    'required': permission,
                    'your_permissions': perms
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ========== Token 管理接口（供前端/用户自己管理，使用JWT认证）==========

@openclaw_bp.route('/openclaw/token', methods=['POST'])
@jwt_required()
def create_token():
    """生成新的 OpenClaw Token
    支持指定有效期（1/3/6 个月）和自定义权限范围。
    """
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json() or {}
    name = data.get('name', 'OpenClaw').strip() or 'OpenClaw'

    # 有效期：1 / 3 / 6 个月
    expires_in_months = data.get('expires_in_months', 3)
    if expires_in_months not in (1, 3, 6):
        return jsonify({'error': '有效期必须是 1、3 或 6 个月'}), 400

    days = expires_in_months * 30
    expires_at = datetime.utcnow() + timedelta(days=days)

    # 权限：默认全部，可自定义子集
    requested_permissions = data.get('permissions')
    if requested_permissions is not None:
        valid_keys = {p['key'] for p in ALL_OPENCLAW_PERMISSIONS}
        invalid = set(requested_permissions) - valid_keys
        if invalid:
            return jsonify({'error': f'包含无效权限: {list(invalid)}'}), 400
        permissions = list(requested_permissions)
    else:
        permissions = DEFAULT_OPENCLAW_PERMISSIONS.copy()

    # 生成随机 Token（用户只会在创建时看到一次明文）
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    token_record = OpenClawToken(
        user_id=user.id,
        token_hash=token_hash,
        name=name,
        expires_at=expires_at,
        permissions=json.dumps(permissions)
    )
    db.session.add(token_record)
    db.session.commit()

    return jsonify({
        'message': 'Token 创建成功（请立即复制，之后无法再次查看）',
        'token': raw_token,
        'token_info': token_record.to_dict()
    }), 201


@openclaw_bp.route('/openclaw/tokens', methods=['GET'])
@jwt_required()
def list_tokens():
    """列出当前用户的所有 Token（不返回明文）"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    tokens = OpenClawToken.query.filter_by(user_id=user.id).order_by(OpenClawToken.created_at.desc()).all()
    return jsonify({'tokens': [t.to_dict() for t in tokens]}), 200


@openclaw_bp.route('/openclaw/token/<int:token_id>', methods=['DELETE'])
@jwt_required()
def revoke_token(token_id):
    """撤销指定 Token"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    token_record = OpenClawToken.query.filter_by(id=token_id, user_id=user.id).first()
    if not token_record:
        return jsonify({'error': 'Token 不存在'}), 404

    token_record.is_active = False
    db.session.commit()
    return jsonify({'message': 'Token 已撤销'}), 200


@openclaw_bp.route('/openclaw/permissions', methods=['GET'])
@jwt_required()
def get_available_permissions():
    """获取所有可选的权限列表（供前端展示）"""
    return jsonify({
        'permissions': ALL_OPENCLAW_PERMISSIONS,
        'defaults': DEFAULT_OPENCLAW_PERMISSIONS
    }), 200


# ========== OpenClaw 数据查询接口 ==========

@openclaw_bp.route('/openclaw/courses', methods=['GET'])
@openclaw_auth_required
@require_permission('read:courses')
def get_courses():
    """获取课程列表（含当前用户进度）"""
    user = g.current_user
    category = request.args.get('category', '')
    search = request.args.get('search', '')

    query = Course.query
    if category:
        query = query.filter(Course.category == category)
    if search:
        query = query.filter(
            Course.title.contains(search) |
            Course.description.contains(search)
        )

    courses = query.order_by(Course.created_at.desc()).all()
    result = []

    for course in courses:
        data = course.to_dict(with_audios=False)
        # 计算该用户在该课程的进度
        audios = AudioFile.query.filter_by(course_id=course.id).all()
        total_duration = sum(a.duration for a in audios)
        listened_duration = 0
        completed_count = 0
        last_study = None

        for audio in audios:
            prog = PlaybackProgress.query.filter_by(user_id=user.id, audio_id=audio.id).first()
            if prog:
                listened_duration += min(prog.current_time, audio.duration)
                if prog.completed:
                    completed_count += 1
                if prog.last_played_at:
                    if last_study is None or prog.last_played_at > last_study:
                        last_study = prog.last_played_at

        data['progress_percent'] = round(listened_duration / total_duration * 100, 1) if total_duration > 0 else 0
        data['completed_audio_count'] = completed_count
        data['total_audio_count'] = len(audios)
        data['listened_minutes'] = round(listened_duration / 60, 1)
        data['total_minutes'] = round(total_duration / 60, 1)
        data['last_study_at'] = last_study.isoformat() if last_study else None
        result.append(data)

    return jsonify({
        'courses': result,
        'categories': list(set([c.category for c in Course.query.with_entities(Course.category).distinct().all()]))
    }), 200


@openclaw_bp.route('/openclaw/progress', methods=['GET'])
@openclaw_auth_required
@require_permission('read:progress')
def get_progress():
    """获取用户总学习进度"""
    user = g.current_user

    progress_list = PlaybackProgress.query.filter_by(user_id=user.id).all()
    total_listened = 0
    total_duration = 0
    completed_audios = 0
    course_ids = set()
    last_study = None

    for p in progress_list:
        audio = AudioFile.query.get(p.audio_id)
        if not audio:
            continue
        course_ids.add(audio.course_id)
        total_listened += min(p.current_time, audio.duration)
        total_duration += audio.duration
        if p.completed:
            completed_audios += 1
        if p.last_played_at:
            if last_study is None or p.last_played_at > last_study:
                last_study = p.last_played_at

    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'total_study_minutes': round(total_listened / 60, 1),
        'total_course_duration_minutes': round(total_duration / 60, 1),
        'overall_progress_percent': round(total_listened / total_duration * 100, 1) if total_duration > 0 else 0,
        'completed_audios': completed_audios,
        'total_audios_played': len(progress_list),
        'courses_enrolled': len(course_ids),
        'last_study_at': last_study.isoformat() if last_study else None
    }), 200


@openclaw_bp.route('/openclaw/history', methods=['GET'])
@openclaw_auth_required
@require_permission('read:history')
def get_history():
    """获取学习历史"""
    user = g.current_user
    days = request.args.get('days', 30, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    logs = StudyLog.query.filter(
        StudyLog.user_id == user.id,
        StudyLog.created_at >= since
    ).order_by(StudyLog.created_at.desc()).all()

    result = []
    for log in logs:
        audio = AudioFile.query.get(log.audio_id)
        course = Course.query.get(log.course_id) if log.course_id else None
        result.append({
            'id': log.id,
            'action': log.action,
            'position': log.position,
            'duration_listened': log.duration_listened,
            'created_at': log.created_at.isoformat() if log.created_at else None,
            'audio': {
                'id': audio.id if audio else None,
                'title': audio.title if audio else '未知音频'
            },
            'course': {
                'id': course.id if course else None,
                'title': course.title if course else '未知课程'
            }
        })

    return jsonify({
        'history': result,
        'period_days': days,
        'total_logs': len(result)
    }), 200


@openclaw_bp.route('/openclaw/stats', methods=['GET'])
@openclaw_auth_required
@require_permission('read:stats')
def get_stats():
    """获取学习统计（7/30/全部）"""
    user = g.current_user
    now = datetime.utcnow()
    stats = {}

    for period_name, days in [('last_7_days', 7), ('last_30_days', 30), ('all_time', 365*10)]:
        since = now - timedelta(days=days)

        progress_records = PlaybackProgress.query.filter(
            PlaybackProgress.user_id == user.id,
            PlaybackProgress.last_played_at >= since
        ).all()

        study_logs = StudyLog.query.filter(
            StudyLog.user_id == user.id,
            StudyLog.created_at >= since
        ).all()

        total_listened = 0
        total_duration = 0
        completed_count = 0
        unique_courses = set()
        unique_audios = set()

        for p in progress_records:
            audio = AudioFile.query.get(p.audio_id)
            if audio:
                unique_audios.add(p.audio_id)
                unique_courses.add(audio.course_id)
                total_listened += min(p.current_time, audio.duration)
                total_duration += audio.duration
                if p.completed:
                    completed_count += 1

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

    return jsonify({'stats': stats, 'user': user.to_dict()}), 200


@openclaw_bp.route('/openclaw/reminder', methods=['GET'])
@openclaw_auth_required
@require_permission('read:reminder')
def get_reminder():
    """获取今日/本周督促提醒 - 核心接口"""
    user = g.current_user
    reminder_type = request.args.get('type', 'daily')  # daily / weekly

    today = date.today()
    if reminder_type == 'weekly':
        week_start = today - timedelta(days=today.weekday())
        since = datetime.combine(week_start, datetime.min.time())
        plan = StudyPlan.query.filter(
            StudyPlan.user_id == user.id,
            StudyPlan.plan_type == 'weekly',
            StudyPlan.target_date == week_start,
            StudyPlan.status == 'active'
        ).first()
    else:
        since = datetime.combine(today, datetime.min.time())
        plan = StudyPlan.query.filter(
            StudyPlan.user_id == user.id,
            StudyPlan.plan_type == 'daily',
            StudyPlan.target_date == today,
            StudyPlan.status == 'active'
        ).first()

    # 计算实际学习时长
    study_logs = StudyLog.query.filter(
        StudyLog.user_id == user.id,
        StudyLog.created_at >= since
    ).all()
    actual_minutes = round(sum(l.duration_listened for l in study_logs) / 60, 1)

    planned_minutes = plan.target_minutes if plan else (30 if reminder_type == 'daily' else 180)
    completion_rate = round(actual_minutes / planned_minutes * 100, 1) if planned_minutes > 0 else 0

    # 获取所有课程进度
    courses = Course.query.all()
    course_progress = []
    for course in courses:
        audios = AudioFile.query.filter_by(course_id=course.id).all()
        if not audios:
            continue
        total_duration = sum(a.duration for a in audios)
        listened_duration = 0
        completed_count = 0
        last_study = None
        for audio in audios:
            prog = PlaybackProgress.query.filter_by(user_id=user.id, audio_id=audio.id).first()
            if prog:
                listened_duration += min(prog.current_time, audio.duration)
                if prog.completed:
                    completed_count += 1
                if prog.last_played_at:
                    if last_study is None or prog.last_played_at > last_study:
                        last_study = prog.last_played_at

        progress_percent = round(listened_duration / total_duration * 100, 1) if total_duration > 0 else 0
        course_progress.append({
            'course_id': course.id,
            'course_title': course.title,
            'category': course.category,
            'progress_percent': progress_percent,
            'completed_audio_count': completed_count,
            'total_audio_count': len(audios),
            'remaining_minutes': round((total_duration - listened_duration) / 60, 1),
            'last_study_date': last_study.strftime('%Y-%m-%d') if last_study else None,
            'days_since': (today - last_study.date()).days if last_study else None
        })

    # 优先推荐：进度最高但未完成
    incomplete = [c for c in course_progress if 0 < c['progress_percent'] < 100]
    incomplete.sort(key=lambda x: x['progress_percent'], reverse=True)
    priority_actions = []
    if incomplete:
        top = incomplete[0]
        priority_actions.append({
            'type': 'continue_course',
            'course_id': top['course_id'],
            'course_title': top['course_title'],
            'progress_percent': top['progress_percent'],
            'suggested_minutes': min(top['remaining_minutes'], 20),
            'reason': f'进度已达 {top["progress_percent"]}%，建议优先完成'
        })

    # 薄弱环节：最久未学且进度<100%
    stale = [c for c in course_progress
             if c['last_study_date'] is not None
             and c['progress_percent'] < 100
             and c['progress_percent'] > 0]
    stale.sort(key=lambda x: x['last_study_date'] or '9999')
    stale_courses = []
    if stale and stale[0]['days_since'] and stale[0]['days_since'] >= 3:
        stale_courses.append({
            'course_id': stale[0]['course_id'],
            'course_title': stale[0]['course_title'],
            'last_study_date': stale[0]['last_study_date'],
            'days_since': stale[0]['days_since'],
            'suggestion': f'已 {stale[0]["days_since"]} 天未学，根据遗忘曲线建议复习'
        })

    # 鼓励语
    if completion_rate >= 100:
        encouragement = f'太棒了！已完成今日目标（{actual_minutes} 分钟），超额完成！'
    elif completion_rate >= 50:
        encouragement = f'已完成 {actual_minutes} 分钟，再坚持 {round(planned_minutes - actual_minutes, 1)} 分钟即可达标！'
    elif actual_minutes > 0:
        encouragement = f'已完成 {actual_minutes} 分钟，还差 {round(planned_minutes - actual_minutes, 1)} 分钟，加油！'
    else:
        encouragement = '今天还没有学习记录哦，花 15 分钟开始第一课吧！'

    return jsonify({
        'reminder_type': reminder_type,
        'generated_at': datetime.utcnow().isoformat(),
        'today_progress': {
            'planned_minutes': planned_minutes,
            'actual_minutes': actual_minutes,
            'completion_rate': completion_rate
        },
        'priority_actions': priority_actions,
        'stale_courses': stale_courses,
        'encouragement': encouragement,
        'has_active_plan': plan is not None
    }), 200


# ========== 学习计划接口 ==========

@openclaw_bp.route('/openclaw/plan', methods=['POST'])
@openclaw_auth_required
@require_permission('write:plan')
def create_plan():
    """创建学习计划"""
    user = g.current_user
    data = request.get_json() or {}

    plan_type = data.get('plan_type', 'daily')
    target_date_str = data.get('target_date')
    target_minutes = data.get('target_minutes', 30)
    target_courses = data.get('target_courses', [])
    focus_areas = data.get('focus_areas', [])
    note = data.get('note', '')

    if plan_type not in ('daily', 'weekly'):
        return jsonify({'error': 'plan_type 必须是 daily 或 weekly'}), 400

    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'target_date 格式应为 YYYY-MM-DD'}), 400
    else:
        target_date = date.today()

    # 检查是否已存在同类型同日期计划
    existing = StudyPlan.query.filter_by(
        user_id=user.id, plan_type=plan_type, target_date=target_date, status='active'
    ).first()
    if existing:
        existing.status = 'replaced'
        db.session.commit()

    plan = StudyPlan(
        user_id=user.id,
        plan_type=plan_type,
        target_date=target_date,
        target_minutes=target_minutes,
        target_courses=json.dumps(target_courses),
        focus_areas=json.dumps(focus_areas),
        note=note
    )
    db.session.add(plan)
    db.session.commit()

    return jsonify({
        'message': '学习计划创建成功',
        'plan': plan.to_dict()
    }), 201


@openclaw_bp.route('/openclaw/plan', methods=['GET'])
@openclaw_auth_required
@require_permission('read:plan')
def get_plan():
    """获取当前学习计划"""
    user = g.current_user
    plan_type = request.args.get('type', 'daily')
    target_date_str = request.args.get('date')

    query = StudyPlan.query.filter_by(user_id=user.id, plan_type=plan_type)
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            query = query.filter_by(target_date=target_date)
        except ValueError:
            return jsonify({'error': 'date 格式应为 YYYY-MM-DD'}), 400
    else:
        query = query.filter(StudyPlan.target_date <= date.today())

    plan = query.order_by(StudyPlan.target_date.desc()).first()

    if not plan:
        return jsonify({'plan': None, 'message': '暂无学习计划'}), 200

    return jsonify({'plan': plan.to_dict()}), 200


@openclaw_bp.route('/openclaw/plan/<int:plan_id>', methods=['PUT'])
@openclaw_auth_required
@require_permission('write:plan')
def update_plan(plan_id):
    """更新学习计划"""
    user = g.current_user
    plan = StudyPlan.query.filter_by(id=plan_id, user_id=user.id).first()
    if not plan:
        return jsonify({'error': '计划不存在'}), 404

    data = request.get_json() or {}
    if 'target_minutes' in data:
        plan.target_minutes = data['target_minutes']
    if 'target_courses' in data:
        plan.target_courses = json.dumps(data['target_courses'])
    if 'focus_areas' in data:
        plan.focus_areas = json.dumps(data['focus_areas'])
    if 'status' in data:
        plan.status = data['status']
    if 'note' in data:
        plan.note = data['note']

    plan.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': '计划已更新', 'plan': plan.to_dict()}), 200


@openclaw_bp.route('/openclaw/progress', methods=['POST'])
@openclaw_auth_required
@require_permission('write:progress')
def update_progress():
    """OpenClaw 上报/更新学习进度"""
    user = g.current_user
    data = request.get_json() or {}

    audio_id = data.get('audio_id')
    current_time = data.get('current_time', 0.0)
    completed = data.get('completed', False)
    duration_listened = data.get('duration_listened', 0.0)

    if not audio_id:
        return jsonify({'error': 'audio_id 必填'}), 400

    audio = AudioFile.query.get(audio_id)
    if not audio:
        return jsonify({'error': '音频不存在'}), 404

    # 更新播放进度
    progress = PlaybackProgress.query.filter_by(user_id=user.id, audio_id=audio_id).first()
    now = datetime.utcnow()

    if progress:
        progress.current_time = current_time
        progress.completed = completed
        progress.last_played_at = now
        if completed:
            progress.play_count += 1
    else:
        progress = PlaybackProgress(
            user_id=user.id,
            audio_id=audio_id,
            current_time=current_time,
            completed=completed,
            last_played_at=now,
            play_count=1
        )
        db.session.add(progress)

    # 记录学习日志
    log = StudyLog(
        user_id=user.id,
        audio_id=audio_id,
        course_id=audio.course_id,
        action='complete' if completed else 'progress',
        position=current_time,
        duration_listened=duration_listened
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'message': '进度已更新',
        'audio_id': audio_id,
        'current_time': current_time,
        'completed': completed
    }), 200
