
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .. import db, limiter
from ..services.user_service import UserService
from ..forms import RegisterForm, LoginForm

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    # 处理JSON API请求
    if request.is_json:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': '需要用户名和密码'}), 400
            
        user = UserService(db.session).get_user_by_username(data['username'])
        
        if user and user.check_password(data['password']):
            if user.status != 'approved':
                return jsonify({'error': '账号未审核'}), 403
            
            login_user(user, remember=data.get('remember', False))
            return jsonify({
                'message': '登录成功',
                'access_token': user.generate_auth_token(),
                'user': user.to_dict()
            })
            
        return jsonify({'error': '用户名或密码错误'}), 401
    
    # 处理表单请求
    form = LoginForm()
    if form.validate_on_submit():
        if not form.username.data or not form.password.data:
            flash('请输入用户名和密码', 'danger')
            return redirect(url_for('auth.login'))
            
        user = UserService(db.session).get_user_by_username(form.username.data)
        
        if user and user.check_password(form.password.data):
            if user.status != 'approved':
                flash('您的账号尚未通过审核', 'warning')
                return redirect(url_for('auth.login'))
            
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        
        flash('用户名或密码错误', 'danger')
    
    return render_template('login.html', form=form)

@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # 处理JSON API请求
    if request.is_json:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': '需要用户名和密码'}), 400
            
        try:
            user = UserService(db.session).create_user(
                password=data['password'],
                username=data['username'],
                is_admin=False,
                status='pending'
            )
            return jsonify({
                'message': '注册成功，请等待管理员审核',
                'user': user.to_dict()
            }), 201
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"用户注册异常: {str(e)}")
            return jsonify({'error': '注册失败，请稍后再试'}), 500
    
    # 处理表单请求
    form = RegisterForm()
    if request.method == 'POST':
        if not form.validate():
            return render_template('register.html', form=form), 400
            
        try:
            if not form.password.data:
                raise ValueError('密码不能为空')
            # 表单验证已确保username存在，这里添加类型断言
            username = str(form.username.data)
            password = str(form.password.data)
            UserService(db.session).create_user(
                password=password,
                username=username,
                is_admin=False,
                status='pending'
            )
            flash('注册成功，请等待管理员审核', 'success')
            return redirect(url_for('auth.login'))
        except ValueError as e:
            flash(f'注册失败: {str(e)}', 'danger')
            return render_template('register.html', form=form), 400
        except Exception as e:
            current_app.logger.error(f"用户注册异常: {str(e)}")
            flash('注册失败，请稍后再试', 'danger')
            return render_template('register.html', form=form), 500
    
    return render_template('register.html', form=form)
