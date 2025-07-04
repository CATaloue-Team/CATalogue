
from functools import wraps
from flask import redirect, url_for, request, abort, flash
from flask_login import current_user
from sqlalchemy import inspect
from app.models import db

def owner_required(model, id_param: str = 'id'):
    """验证当前用户是否是资源所有者
    Args:
        model: SQLAlchemy模型类
        id_param: URL参数中资源ID的键名
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查资源有效性
            if not hasattr(model, 'query'):
                flash('无效的资源类型', 'error')
                return redirect(url_for('main.index'))

            # 获取资源ID
            resource_id = kwargs.get(id_param)
            if not resource_id:
                flash('缺少资源ID', 'error')
                return redirect(url_for('main.index'))
                
            # 查询资源
            resource = model.query.get(resource_id)
            if not resource:
                flash('资源不存在', 'error')
                return redirect(url_for('main.index'))
                
            # 检查登录状态
            if not current_user.is_authenticated:
                flash('请先登录', 'error')
                return redirect(url_for('auth.login'))

            # 管理员直接放行
            if current_user.is_admin:
                return f(*args, **kwargs)

            # 检查资源所有权
            if current_user.id != resource.user_id:
                flash('无权访问该资源', 'error')
                return redirect(url_for('main.index'))

            # 所有检查通过后执行原函数
            return f(*args, **kwargs)
        return decorated_function
    return decorator
import logging
from typing import Any
import json
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)
logger.debug("装饰器模块已加载")

def validate_schema(schema: dict[str, Any]):
    """验证请求数据是否符合JSON Schema"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.json:
                abort(400, description="Request must be JSON")
            try:
                validate(instance=request.json, schema=schema)
            except ValidationError as e:
                abort(400, description=str(e))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def prevent_self_operation(f):
    """防止管理员自我操作装饰器"""
    logger.debug(f"创建prevent_self_operation装饰器，应用于函数: {f.__name__}")
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.debug(f"执行prevent_self_operation检查，参数: {kwargs}")
        # 检查参数中的id或user_id是否匹配当前用户或用户未登录
        target_id = kwargs.get('user_id') or kwargs.get('id')
        if not current_user.is_authenticated or (target_id and str(target_id) == str(current_user.id)):
            logger.warning("检测到管理员自我操作尝试或未登录用户")
            flash('不能对自己执行此操作', 'danger')
            return redirect(url_for('admin.UserCRUD_list'))
        return f(*args, **kwargs)
    return decorated_function
