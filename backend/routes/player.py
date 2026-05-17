from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

try:
    from backend.models import db, User, AudioFile, Course, PlaybackProgress, StudyLog
except ImportError:
    from models import db, User, AudioFile, Course, PlaybackProgress, StudyLog

player_bp = Blueprint('player', __name__)


@player_bp.route('/progress/<int:audio_id>', methods=['GET'])
@jwt_required()
def get_progress(audio_id):
    """获取用户对某个音频的播放进度"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    audio = AudioFile.query.get(audio_id)
    if not audio:
        return jsonify({'error': '音频不存在'}), 404

    progress = PlaybackProgress.query.filter_by(
        user_id=user.id, audio_id=audio_id
    ).first()

    if not progress:
        return jsonify({
            'audio_id': audio_id,
            'current_time': 0.0,
            'completed': False,
            'play_count': 0,
            'total_duration': audio.duration
        }), 200

    return jsonify({
        'audio_id': audio_id,
        'current_time': progress.current_time,
        'completed': progress.completed,
        'play_count': progress.play_count,
        'last_played_at': progress.last_played_at.isoformat() if progress.last_played_at else None,
        'total_duration': audio.duration
    }), 200


@player_bp.route('/progress/<int:audio_id>', methods=['POST'])
@jwt_required()
def update_progress(audio_id):
    """更新播放进度 - 支持断点续播"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    audio = AudioFile.query.get(audio_id)
    if not audio:
        return jsonify({'error': '音频不存在'}), 404

    data = request.get_json()
    current_time = data.get('current_time', 0.0)
    completed = data.get('completed', False)

    # 验证 current_time 在合理范围
    if current_time < 0:
        current_time = 0.0

    # 查找或创建进度记录
    progress = PlaybackProgress.query.filter_by(
        user_id=user.id, audio_id=audio_id
    ).first()

    now = datetime.utcnow()

    if progress:
        progress.current_time = current_time
        progress.completed = completed
        progress.last_played_at = now
        if completed and not progress.completed:
            progress.play_count += 1
    else:
        progress = PlaybackProgress(
            user_id=user.id,
            audio_id=audio_id,
            current_time=current_time,
            completed=completed,
            last_played_at=now,
            play_count=1 if completed else 1
        )
        db.session.add(progress)

    db.session.commit()

    return jsonify({
        'message': '进度已更新',
        'audio_id': audio_id,
        'current_time': current_time,
        'completed': completed
    }), 200


@player_bp.route('/progress', methods=['POST'])
@jwt_required()
def log_study_action():
    """记录学习行为日志 - 用于学习分析"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json()
    audio_id = data.get('audio_id')
    action = data.get('action')  # play / pause / complete / seek
    position = data.get('position', 0.0)
    duration_listened = data.get('duration_listened', 0.0)

    audio = AudioFile.query.get(audio_id)
    if not audio:
        return jsonify({'error': '音频不存在'}), 404

    log = StudyLog(
        user_id=user.id,
        audio_id=audio_id,
        course_id=audio.course_id,
        action=action,
        position=position,
        duration_listened=duration_listened
    )

    db.session.add(log)
    db.session.commit()

    return jsonify({'message': '学习行为已记录'}), 201


@player_bp.route('/progress/all', methods=['GET'])
@jwt_required()
def get_all_progress():
    """获取用户所有课程的播放进度"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    # 获取用户所有进度记录
    progress_list = PlaybackProgress.query.filter_by(user_id=user.id).all()

    # 按课程分组统计
    course_stats = {}
    for p in progress_list:
        audio = AudioFile.query.get(p.audio_id)
        if not audio:
            continue
        course_id = audio.course_id
        if course_id not in course_stats:
            course_stats[course_id] = {
                'total_audio': 0,
                'completed_audio': 0,
                'total_duration': 0.0,
                'listened_duration': 0.0
            }
        course_stats[course_id]['total_audio'] += 1
        course_stats[course_id]['total_duration'] += audio.duration
        if p.completed:
            course_stats[course_id]['completed_audio'] += 1
        course_stats[course_id]['listened_duration'] += min(p.current_time, audio.duration)

    # 加入课程信息
    result = []
    for course_id, stats in course_stats.items():
        course = Course.query.get(course_id)
        if course:
            result.append({
                'course_id': course_id,
                'course_title': course.title,
                'cover_image': course.cover_image,
                'progress_percent': round(
                    stats['listened_duration'] / stats['total_duration'] * 100, 1
                ) if stats['total_duration'] > 0 else 0,
                'completed_percent': round(
                    stats['completed_audio'] / stats['total_audio'] * 100, 1
                ) if stats['total_audio'] > 0 else 0,
                'total_audio': stats['total_audio'],
                'completed_audio': stats['completed_audio']
            })

    return jsonify({'courses_progress': result}), 200


@player_bp.route('/audio/<int:audio_id>/stream')
def stream_audio(audio_id):
    """音频流服务 - 支持范围请求（断点续传播放）"""
    from flask import send_file, abort
    import os

    audio = AudioFile.query.get(audio_id)
    if not audio:
        return jsonify({'error': '音频不存在'}), 404

    # 如果是本地文件，直接提供
    if audio.storage_type == 'local':
        if os.path.exists(audio.file_path):
            return send_file(audio.file_path, mimetype='audio/mpeg')
        else:
            return jsonify({'error': '文件不存在'}), 404

    # 如果是OSS存储，重定向到OSS URL
    if audio.storage_type == 'oss':
        from flask import redirect
        return redirect(audio.file_path)

    return jsonify({'error': '不支持的存储类型'}), 500
