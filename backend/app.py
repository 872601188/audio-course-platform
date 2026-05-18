import os
import sys
from datetime import timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

# 确保项目根目录在 sys.path 中（支持直接运行 app.py）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 兼容两种运行方式：python app.py 和 python -m backend.app
try:
    from backend.models import db, User, Course, AudioFile, PlaybackProgress, StudyLog
except ImportError:
    from models import db, User, Course, AudioFile, PlaybackProgress, StudyLog

# 加载环境变量
load_dotenv()


def create_app():
    """应用工厂函数 - 创建并配置 Flask 应用"""
    app = Flask(__name__, static_folder='../frontend', static_url_path='')

    # ========== SQLite 数据库配置（强制使用 SQLite） ==========
    # 数据库存储在工作区目录，确保持久化
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(base_dir, 'instance')
    os.makedirs(db_dir, exist_ok=True)

    db_path = os.environ.get('SQLITE_DB_PATH', os.path.join(db_dir, 'audio_course.db'))
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # SQLite 需要此配置以支持外键约束检查
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False}
    }

    # JWT 配置
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 最大上传 500MB

    # 文件上传配置
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(base_dir, 'uploads'))
    app.config['ALLOWED_AUDIO_EXTENSIONS'] = {'mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac'}
    app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # 阿里云OSS配置（可选）
    app.config['OSS_ENABLED'] = os.environ.get('OSS_ENABLED', 'false').lower() == 'true'
    app.config['OSS_ACCESS_KEY'] = os.environ.get('OSS_ACCESS_KEY', '')
    app.config['OSS_SECRET_KEY'] = os.environ.get('OSS_SECRET_KEY', '')
    app.config['OSS_ENDPOINT'] = os.environ.get('OSS_ENDPOINT', 'oss-cn-beijing.aliyuncs.com')
    app.config['OSS_BUCKET'] = os.environ.get('OSS_BUCKET', '')

    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'audio'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'covers'), exist_ok=True)

    # 初始化扩展
    db.init_app(app)
    JWTManager(app)
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # 注册蓝图
    try:
        from backend.routes.auth import auth_bp
        from backend.routes.courses import courses_bp
        from backend.routes.upload import upload_bp
        from backend.routes.player import player_bp
        from backend.routes.analyze import analyze_bp
        from backend.routes.openclaw import openclaw_bp
    except ImportError:
        from routes.auth import auth_bp
        from routes.courses import courses_bp
        from routes.upload import upload_bp
        from routes.player import player_bp
        from routes.analyze import analyze_bp
        from routes.openclaw import openclaw_bp

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(courses_bp, url_prefix='/api')
    app.register_blueprint(upload_bp, url_prefix='/api')
    app.register_blueprint(player_bp, url_prefix='/api')
    app.register_blueprint(analyze_bp, url_prefix='/api')
    app.register_blueprint(openclaw_bp, url_prefix='/api')

    # 创建数据库表
    with app.app_context():
        db.create_all()

    # 根路由 - 返回前端首页
    @app.route('/')
    def index():
        return send_from_directory('../frontend', 'index.html')

    @app.route('/<path:path>')
    def serve_frontend(path):
        frontend_dir = os.path.join(os.path.dirname(__file__), '../frontend')
        file_path = os.path.join(frontend_dir, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory('../frontend', path)
        # SPA 路由回退
        if not path.startswith('api/'):
            return send_from_directory('../frontend', 'index.html')
        return jsonify({'error': 'Not found'}), 404

    # 健康检查接口
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'ok',
            'version': '1.0.0',
            'database': 'sqlite',
            'db_path': db_path
        })

    # 全局错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': '接口不存在'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': '服务器内部错误'}), 500

    return app


# 创建应用实例
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
