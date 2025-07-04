from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache
from flask_babel import Babel
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager

# 从database模块导入db实例
from .database import db
migrate = Migrate()
login_manager = LoginManager()
cache = Cache()
babel = Babel()
jwt = JWTManager()

def init_app(app):
    babel.init_app(app)
    app.config['BABEL_DEFAULT_LOCALE'] = 'zh'
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
csrf = CSRFProtect()

# 配置限流存储
from redis import Redis
import os
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
storage_uri = redis_url if os.getenv('FLASK_ENV') == 'production' else 'memory://'

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=storage_uri
)
