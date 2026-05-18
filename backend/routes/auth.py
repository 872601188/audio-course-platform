from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

try:
    from backend.models import db, User
except ImportError:
    from models import db, User

from datetime import datetime

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册接口"""
    data = request.get_json()

    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'student')

    # 验证必填字段
    if not username or not email or not password:
        return jsonify({'error': '用户名、邮箱和密码不能为空'}), 400

    if len(password) < 6:
        return jsonify({'error': '密码长度至少6位'}), 400

    if role not in ['student', 'admin']:
        role = 'student'

    # 检查用户名和邮箱是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已注册'}), 409

    # 创建新用户
    new_user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        'message': '注册成功',
        'user': new_user.to_dict()
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录接口"""
    data = request.get_json()

    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    # 支持用户名或邮箱登录
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': '用户名或密码错误'}), 401

    # 生成 JWT Token
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': '登录成功',
        'access_token': access_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """获取当前登录用户信息"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user:
        return jsonify({'error': '用户不存在'}), 404

    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """获取用户列表（仅管理员）"""
    user_id = get_jwt_identity()
    current_user = User.query.get(int(user_id))

    if not current_user or current_user.role != 'admin':
        return jsonify({'error': '权限不足'}), 403

    users = User.query.all()
    return jsonify({'users': [u.to_dict() for u in users]}), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """修改密码"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not check_password_hash(user.password_hash, old_password):
        return jsonify({'error': '原密码错误'}), 400

    if len(new_password) < 6:
        return jsonify({'error': '新密码长度至少6位'}), 400

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({'message': '密码修改成功'}), 200


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_profile():
    """更新当前用户个人信息"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))

    if not user:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json() or {}

    # 更新用户名
    new_username = data.get('username', '').strip()
    if new_username and new_username != user.username:
        if User.query.filter_by(username=new_username).first():
            return jsonify({'error': '用户名已被占用'}), 409
        user.username = new_username

    # 更新邮箱
    new_email = data.get('email', '').strip()
    if new_email and new_email != user.email:
        if User.query.filter_by(email=new_email).first():
            return jsonify({'error': '邮箱已被注册'}), 409
        user.email = new_email

    # 更新手机号
    new_phone = data.get('phone', '').strip() or None
    if new_phone and new_phone != user.phone:
        if User.query.filter_by(phone=new_phone).first():
            return jsonify({'error': '手机号已被绑定'}), 409
        user.phone = new_phone

    db.session.commit()

    return jsonify({
        'message': '个人信息更新成功',
        'user': user.to_dict()
    }), 200
