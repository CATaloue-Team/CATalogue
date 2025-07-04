from flask import Flask as BaseFlask, request
from typing import Any, Optional, TypeVar, cast
from werkzeug.wrappers import Response as BaseResponse
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# 从extensions导入db实例
from .extensions import db

# 在创建应用前导入所有模型
from .models import User, Cat
from flask_restx import Api, Resource, Namespace, fields
from .extensions import cache, login_manager, csrf, limiter, babel
from app.services.cat_service import CatService
from .services.user_service import UserService
from .middlewares.error_handler import register_error_handlers

# 自定义Flask类添加类型注解
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .services.user_service import UserService
    from .services.cat_service import CatService

class Flask(BaseFlask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: SQLAlchemy
        self.cat_service: 'CatService' = None  # type: ignore
        self.user_service: 'UserService' = None  # type: ignore
        self.cat_crud: 'BaseCRUD' = None  # type: ignore

class Response(BaseResponse):
    pass

from sentry_sdk.integrations.flask import FlaskIntegration
import sentry_sdk
from werkzeug.middleware.proxy_fix import ProxyFix
from logging.handlers import RotatingFileHandler
import logging
import time
from .config import Config
import os

# 确保类型检查器知道这是我们的自定义类
T = TypeVar('T', bound=BaseFlask)
def create_flask_app(cls: type[T], *args: Any, **kwargs: Any) -> T:
    return cast(T, cls(*args, **kwargs))

def create_app(config_class=Config):
    app = create_flask_app(Flask, __name__,
              template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates'),
              static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static'))
    app.config.from_object(config_class)
    
    # 将property配置转换为实际值
    for key in dir(config_class):
        if isinstance(getattr(config_class, key, None), property):
            app.config[key] = getattr(config_class(), key)
    
    # 重置日志系统
    app.logger.handlers.clear()
    
    # 简单控制台日志配置
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # 强制测试日志功能
    logging.debug("=== 基本日志系统测试开始 ===")
    logging.debug("这是一条DEBUG级别测试日志")
    logging.info("这是一条INFO级别测试日志")
    logging.warning("这是一条WARNING级别测试日志")
    
    # 添加请求日志中间件
    @app.before_request
    def log_request_info():
        app.logger.info(f"请求开始: {request.method} {request.path}")
        app.logger.debug(f"请求参数: {request.args.to_dict()}")
        app.logger.debug(f"请求头: {dict(request.headers)}")
        
    @app.after_request
    def log_response_info(response):
        duration = time.time() - getattr(request, 'start_time', time.time())
        app.logger.info(
            f"请求完成: {request.method} {request.path} "
            f"状态码:{response.status_code} 耗时:{duration:.3f}s"
        )
        return response
    
    # 初始化扩展
    db_uri = getattr(app.config, 'SQLALCHEMY_DATABASE_URI', '')
    if isinstance(db_uri, str) and db_uri.startswith('sqlite://'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': None}
    
    # 初始化数据库
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # 确保在应用上下文中创建表
    @app.cli.command("create-tables")
    def create_tables():
        """Initialize database tables"""
        with app.app_context():
            db.create_all()
            print("Database tables created successfully")
    
    app.db = db  # type: ignore  # 使db实例可通过app访问
    cache.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    babel.init_app(app)
    from .extensions import jwt
    jwt.init_app(app)
    
    # 配置Babel
    app.config['BABEL_DEFAULT_LOCALE'] = 'zh'
    app.config['BABEL_SUPPORTED_LOCALES'] = ['zh', 'en']
    
    # 初始化Sentry监控
    if app.config.get('SENTRY_DSN'):
        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            integrations=[FlaskIntegration()],
            traces_sample_rate=1.0,
            environment=app.config.get('ENVIRONMENT', 'development')
        )
    
    # 初始化健康检查
    from app.core.health_check import HealthCheck
    health_checker = HealthCheck(app)
    health_checker.register_cli_commands()
    login_manager.login_view = 'auth.login'  # type: ignore
    
    # 代理设置
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    
    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 注册模板路由
    from .routes import main
    main.register_template_routes(app)
    
    # 注册认证路由
    from .routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    # 初始化猫咪路由
    from .routes.cats import init_app as init_cats
    init_cats(app)
    
    # 最后初始化API (确保应用上下文完全建立)
    from .api import api
    with app.app_context():
        api.init_app(app)

    # 注册错误处理器
    register_error_handlers(app)

    # 初始化Swagger API文档 (已通过api/__init__.py配置)
    # 保留此空块以兼容现有代码
    
    # 初始化服务(带日志记录)
    @app.cli.command("init-app")
    def init_app():
        """Initialize application data"""
        with app.app_context():
            from app.services.cat_service import CatService
            from app.services.user_service import UserService
            app.cat_service = CatService(db)  # type: ignore
            app.user_service = UserService(db)  # type: ignore
            from .core.initialization import init_roles, init_admin
            init_roles()
            init_admin()
            app.logger.info("Application initialized successfully")
    
    try:
        with app.app_context():
            from app.services.cat_service import CatService
            from app.services.user_service import UserService
            app.cat_service = CatService(db)  # type: ignore
            app.user_service = UserService(db)  # type: ignore
            app.logger.info("服务初始化成功")
    except Exception as e:
        app.logger.error(f"服务初始化失败: {str(e)}")
        raise
    
    # 在蓝图注册后导入装饰器
    from .decorators import prevent_self_operation
    
    # 生产环境路由监控(测试时跳过)
    if not app.debug and not app.testing and False:  # 测试时强制禁用
        from prometheus_client import Counter, generate_latest
        REQUEST_COUNT = Counter(
            'http_requests_total',
            'HTTP Requests Total',
            ['method', 'endpoint', 'status']
        )
        
        @app.after_request
        def monitor_requests(response):
            if hasattr(request, 'endpoint'):
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=request.endpoint,
                    status=response.status_code
                ).inc()
            return response
            
        @app.route('/metrics')
        def metrics():
            return generate_latest()
    
    # 性能优化中间件
    @app.after_request
    def add_header(response):
        # 静态资源长期缓存+版本控制
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            response.headers['Vary'] = 'Accept-Encoding'
            
            # 为CSS/JS添加内容哈希(仅当不是passthrough模式时)
            if request.path.endswith(('.css', '.js')) and not response.is_sequence:
                try:
                    import hashlib
                    file_hash = hashlib.md5(response.get_data()).hexdigest()[:8]
                    response.headers['ETag'] = f'"{file_hash}"'
                except RuntimeError:
                    # 跳过passthrough模式的响应
                    pass
                
        # 动态内容短期缓存
        elif request.endpoint in ('main.home', 'cats.detail'):
            response.headers['Cache-Control'] = 'public, max-age=60'
            
        # 敏感内容不缓存
        else:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            
        return response
    
    return app

from .models import User

@login_manager.user_loader
def load_user(user_id):
    from app import db
    return db.session.query(User).get(int(user_id))
