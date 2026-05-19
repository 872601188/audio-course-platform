import os
import uuid
import hashlib
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

try:
    from backend.models import db, User, Course, AudioFile
except ImportError:
    from models import db, User, Course, AudioFile


# 预设封面背景色（蓝色系，与参考图风格一致）
COVER_COLORS = [
    (74, 111, 165),   # 经典蓝（参考图）
    (59, 96, 150),    # 深蓝
    (82, 130, 170),   # 亮蓝
    (66, 119, 140),   # 青蓝
    (78, 108, 145),   # 灰蓝
    (52, 92, 135),    # 暗蓝
    (88, 125, 165),   # 浅蓝灰
    (64, 105, 155),   # 中蓝
]


def _get_cover_font(size):
    """尝试加载系统中文字体，找不到则回退默认字体"""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_course_cover(title, category, upload_folder):
    """生成课程封面图：纯色背景 + 居中标题 + 右上角分类标签"""
    width, height = 800, 450

    # 根据标题哈希选择颜色，保证同一课程名颜色一致
    color_index = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16) % len(COVER_COLORS)
    bg_color = COVER_COLORS[color_index]

    # 创建背景
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # 绘制分类标签（右上角圆角深色标签）
    tag_text = category if category else '未分类'
    tag_font = _get_cover_font(22)
    tag_padding_x, tag_padding_y = 16, 6

    bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
    tag_text_w = bbox[2] - bbox[0]
    tag_text_h = bbox[3] - bbox[1]
    tag_w = tag_text_w + tag_padding_x * 2
    tag_h = tag_text_h + tag_padding_y * 2
    tag_x = width - tag_w - 28
    tag_y = 28

    # 用圆角矩形画标签背景（深色半透明）
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [tag_x, tag_y, tag_x + tag_w, tag_y + tag_h],
        radius=tag_h // 2,
        fill=(30, 30, 30, 180)
    )
    img = img.convert('RGBA')
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 标签文字
    draw.text(
        (tag_x + tag_padding_x, tag_y + tag_padding_y - 2),
        tag_text, font=tag_font, fill=(255, 255, 255)
    )

    # 绘制课程标题（居中，自动缩小字号以适应宽度）
    title_font_size = 56
    title_font = _get_cover_font(title_font_size)
    while title_font_size > 24:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        text_w = bbox[2] - bbox[0]
        if text_w <= width - 80:
            break
        title_font_size -= 4
        title_font = _get_cover_font(title_font_size)

    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (width - text_w) // 2
    text_y = (height - text_h) // 2 - 10

    draw.text((text_x, text_y), title, font=title_font, fill=(255, 255, 255))

    # 转回 RGB 并保存
    img = img.convert('RGB')

    filename = f"auto_cover_{uuid.uuid4().hex}.jpg"
    cover_dir = os.path.join(upload_folder, 'covers')
    os.makedirs(cover_dir, exist_ok=True)
    save_path = os.path.join(cover_dir, filename)
    img.save(save_path, 'JPEG', quality=90)

    return f'/uploads/covers/{filename}'

courses_bp = Blueprint('courses', __name__)


@courses_bp.route('/courses', methods=['GET'])
def get_courses():
    """获取课程列表 - 支持分类筛选和搜索"""
    # 查询参数
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Course.query

    if category:
        query = query.filter(Course.category == category)

    if search:
        query = query.filter(
            Course.title.contains(search) |
            Course.description.contains(search)
        )

    # 分页
    pagination = query.order_by(Course.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    courses = pagination.items

    # 如果有登录用户，获取每个课程的播放进度
    try:
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            from models import PlaybackProgress
            for course in courses:
                course_progress = db.session.query(
                    db.func.avg(PlaybackProgress.current_time / AudioFile.duration * 100)
                ).join(AudioFile, PlaybackProgress.audio_id == AudioFile.id).filter(
                    AudioFile.course_id == course.id,
                    PlaybackProgress.user_id == int(user_id)
                ).scalar()
                course._progress = round(course_progress or 0, 1)
    except:
        pass

    result = []
    for course in courses:
        data = course.to_dict()
        if hasattr(course, '_progress'):
            data['progress'] = course._progress
        result.append(data)

    return jsonify({
        'courses': result,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'categories': list(set([c.category for c in Course.query.with_entities(Course.category).distinct().all()]))
    }), 200


@courses_bp.route('/courses/<int:course_id>', methods=['GET'])
def get_course_detail(course_id):
    """获取课程详情 - 包含所有音频文件"""
    course = Course.query.get_or_404(course_id)

    data = course.to_dict(with_audios=True)

    # 如果有登录用户，附加每个音频的播放进度
    try:
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            from models import PlaybackProgress
            for audio in data['audio_files']:
                progress = PlaybackProgress.query.filter_by(
                    user_id=int(user_id),
                    audio_id=audio['id']
                ).first()
                if progress:
                    audio['current_time'] = progress.current_time
                    audio['completed'] = progress.completed
                    audio['play_count'] = progress.play_count
                else:
                    audio['current_time'] = 0
                    audio['completed'] = False
                    audio['play_count'] = 0
    except:
        pass

    return jsonify({'course': data}), 200


@courses_bp.route('/courses', methods=['POST'])
@jwt_required()
def create_course():
    """创建课程 - 仅管理员"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足，仅管理员可创建课程'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    title = data.get('title', '').strip()
    description = data.get('description', '')
    category = data.get('category', '未分类').strip()
    cover_image = data.get('cover_image', '')

    if not title:
        return jsonify({'error': '课程标题不能为空'}), 400

    # 未上传封面时自动生成
    if not cover_image:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'backend/uploads')
        cover_image = generate_course_cover(title, category, upload_folder)

    new_course = Course(
        title=title,
        description=description,
        category=category,
        cover_image=cover_image,
        created_by=int(user_id)
    )

    db.session.add(new_course)
    db.session.commit()

    return jsonify({
        'message': '课程创建成功',
        'course': new_course.to_dict()
    }), 201


@courses_bp.route('/courses/<int:course_id>', methods=['PUT'])
@jwt_required()
def update_course(course_id):
    """更新课程 - 仅管理员"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足'}), 403

    course = Course.query.get_or_404(course_id)
    data = request.get_json()

    course.title = data.get('title', course.title).strip() or course.title
    course.description = data.get('description', course.description)
    course.category = data.get('category', course.category)
    course.cover_image = data.get('cover_image', course.cover_image)

    db.session.commit()

    return jsonify({
        'message': '课程更新成功',
        'course': course.to_dict()
    }), 200


@courses_bp.route('/courses/<int:course_id>', methods=['DELETE'])
@jwt_required()
def delete_course(course_id):
    """删除课程 - 仅管理员（级联删除关联音频）"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足'}), 403

    course = Course.query.get_or_404(course_id)

    # 级联删除音频文件（数据库会自动处理）
    # 但物理文件需要手动删除
    import os
    from flask import current_app
    for audio in course.audio_files:
        if audio.storage_type == 'local' and os.path.exists(audio.file_path):
            try:
                os.remove(audio.file_path)
            except:
                pass

    db.session.delete(course)
    db.session.commit()

    return jsonify({'message': '课程已删除'}), 200


@courses_bp.route('/courses/<int:course_id>/reorder', methods=['POST'])
@jwt_required()
def reorder_audio_files(course_id):
    """重新排序课程下的音频文件"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足'}), 403

    course = Course.query.get_or_404(course_id)
    data = request.get_json()
    audio_orders = data.get('orders', [])  # [{"audio_id": 1, "order_index": 0}, ...]

    for item in audio_orders:
        audio = AudioFile.query.filter_by(id=item['audio_id'], course_id=course_id).first()
        if audio:
            audio.order_index = item['order_index']

    db.session.commit()

    return jsonify({'message': '排序已更新'}), 200
