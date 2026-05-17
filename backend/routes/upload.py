import os
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

try:
    from backend.models import db, User, Course, AudioFile
except ImportError:
    from models import db, User, Course, AudioFile

from PIL import Image

try:
    from mutagen.mp3 import MP3
    from mutagen.wave import WAVE
    from mutagen.oggvorbis import OggVorbis
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    AUDIO_METADATA_AVAILABLE = True
except ImportError:
    AUDIO_METADATA_AVAILABLE = False

upload_bp = Blueprint('upload', __name__)


def allowed_file(filename, allowed_extensions):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_audio_duration(file_path):
    """使用 mutagen 获取音频时长（秒）"""
    if not AUDIO_METADATA_AVAILABLE:
        return 0.0
    try:
        ext = Path(file_path).suffix.lower()
        if ext == '.mp3':
            audio = MP3(file_path)
        elif ext == '.wav':
            audio = WAVE(file_path)
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
        elif ext == '.flac':
            audio = FLAC(file_path)
        elif ext in ('.m4a', '.mp4', '.aac'):
            audio = MP4(file_path)
        else:
            return 0.0
        return audio.info.length
    except Exception as e:
        print(f"获取音频时长失败: {e}")
        return 0.0


def save_file_to_local(file, folder, filename):
    """保存文件到本地目录"""
    save_path = os.path.join(folder, filename)
    file.save(save_path)
    return save_path


def save_to_oss(file, filename):
    """保存文件到阿里云OSS（可选功能）"""
    try:
        import oss2
        access_key = current_app.config.get('OSS_ACCESS_KEY')
        secret_key = current_app.config.get('OSS_SECRET_KEY')
        endpoint = current_app.config.get('OSS_ENDPOINT')
        bucket_name = current_app.config.get('OSS_BUCKET')

        if not all([access_key, secret_key, bucket_name]):
            return None

        auth = oss2.Auth(access_key, secret_key)
        bucket = oss2.Bucket(auth, endpoint, bucket_name)

        # 重置文件指针
        file.seek(0)
        object_key = f'audio-course/{filename}'
        bucket.put_object(object_key, file.read())

        # 返回 OSS URL
        if 'aliyuncs.com' in endpoint:
            return f'https://{bucket_name}.{endpoint}/{object_key}'
        else:
            return f'https://{endpoint}/{bucket_name}/{object_key}'
    except Exception as e:
        print(f"OSS上传失败: {e}")
        return None


@upload_bp.route('/upload/audio', methods=['POST'])
@jwt_required()
def upload_audio():
    """批量上传音频文件 - 支持多文件拖拽上传"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足'}), 403

    # 检查是否有 course_id 参数
    course_id = request.form.get('course_id', type=int)
    if not course_id:
        return jsonify({'error': '必须指定课程ID'}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    # 获取上传的文件列表
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': '未选择任何文件'}), 400

    uploaded_files = []
    errors = []

    for file in files:
        if file.filename == '':
            continue

        if not allowed_file(file.filename, current_app.config['ALLOWED_AUDIO_EXTENSIONS']):
            errors.append(f"{file.filename}: 不支持的文件格式")
            continue

        # 生成唯一文件名
        original_name = file.filename
        ext = original_name.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{ext}"

        # 保存到本地
        audio_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        local_path = save_file_to_local(file, audio_dir, unique_filename)

        # 尝试上传到OSS（如果配置启用）
        storage_type = 'local'
        file_path = local_path
        oss_url = None

        if current_app.config.get('OSS_ENABLED', False):
            file.seek(0)  # 重置文件指针
            oss_url = save_to_oss(file, unique_filename)
            if oss_url:
                storage_type = 'oss'
                file_path = oss_url

        # 获取音频时长
        duration = get_audio_duration(local_path)

        # 从表单获取音频标题（如果有），否则使用原始文件名（去掉扩展名）
        title = request.form.get(f'title_{len(uploaded_files)}', '').strip()
        if not title:
            title = original_name.rsplit('.', 1)[0]

        # 获取当前最大排序索引
        max_order = db.session.query(db.func.max(AudioFile.order_index)).filter_by(
            course_id=course_id
        ).scalar() or -1

        # 创建音频记录
        audio_file = AudioFile(
            course_id=course_id,
            title=title,
            filename=unique_filename,
            original_name=original_name,
            duration=duration,
            file_path=file_path,
            storage_type=storage_type,
            order_index=max_order + 1
        )

        db.session.add(audio_file)
        db.session.flush()  # 获取 ID

        uploaded_files.append({
            'id': audio_file.id,
            'title': audio_file.title,
            'original_name': original_name,
            'duration': duration,
            'file_path': file_path,
            'storage_type': storage_type
        })

    db.session.commit()

    return jsonify({
        'message': f'成功上传 {len(uploaded_files)} 个文件',
        'uploaded': uploaded_files,
        'errors': errors
    }), 201


@upload_bp.route('/upload/cover', methods=['POST'])
@jwt_required()
def upload_cover():
    """上传课程封面图片"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足'}), 403

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    if not allowed_file(file.filename, current_app.config['ALLOWED_IMAGE_EXTENSIONS']):
        return jsonify({'error': '不支持的图片格式'}), 400

    # 处理图片
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"cover_{uuid.uuid4().hex}.{ext}"

    cover_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'covers')
    os.makedirs(cover_dir, exist_ok=True)

    # 保存并压缩图片
    save_path = os.path.join(cover_dir, unique_filename)
    try:
        img = Image.open(file.stream)
        # 限制最大尺寸
        max_size = (800, 600)
        img.thumbnail(max_size, Image.LANCZOS)
        # 转换为 RGB（处理透明通道）
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(save_path, 'JPEG', quality=85)
    except Exception as e:
        # 如果PIL处理失败，直接保存
        file.seek(0)
        file.save(save_path)

    # 构建返回URL
    relative_path = f'/uploads/covers/{unique_filename}'

    return jsonify({
        'message': '封面上传成功',
        'url': relative_path,
        'filename': unique_filename
    }), 201


@upload_bp.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """提供本地上传文件的访问"""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename)


# 兼容 Flask 的 send_from_directory 导入
from flask import send_from_directory
