from flask import request
from flask_login import current_user
from flask_restx import Namespace, Resource, fields
from .. import db
from ..services.cat_service import CatService
from ..models import Cat

api = Namespace('cats', description='猫咪管理相关操作')

cat_model = api.model('Cat', {
    'id': fields.Integer(description='猫咪ID'),
    'name': fields.String(required=True, description='猫咪名字'),
    'breed': fields.String(description='品种'),
    'age': fields.Integer(description='年龄'),
    'description': fields.String(description='描述'),
    'is_adopted': fields.Boolean(description='是否被领养'),
    'created_at': fields.DateTime(description='创建时间'),
    'updated_at': fields.DateTime(description='更新时间'),
    'user_id': fields.Integer(description='所属用户ID')
})

cat_create_model = api.model('CatCreate', {
    'name': fields.String(required=True),
    'breed': fields.String(required=True),
    'age': fields.Integer(required=True),
    'description': fields.String(),
    'is_adopted': fields.Boolean(default=False),
    'user_id': fields.Integer()
})

@api.route('/')
class CatList(Resource):
    @api.doc(security='Bearer Auth')
    @api.marshal_list_with(cat_model)
    def get(self):
        """获取所有猫咪列表"""
        return CatService(db).search()

    @api.doc(security='Bearer Auth')
    @api.expect(cat_create_model)
    @api.marshal_with(cat_model, code=201)  # type: ignore
    def post(self):
        """创建新猫咪"""
        data = api.payload
        try:
            cat = CatService(db).create_cat(
                name=data['name'],
                breed=data['breed'],
                age=data['age'],
                description=data.get('description', ''),
                is_adopted=data.get('is_adopted', False),
                user_id=data.get('user_id', current_user.id if current_user.is_authenticated else None),
            )
            return cat, 201
        except ValueError as e:
            api.abort(400, str(e))
        except Exception as e:
            api.abort(500, str(e))

@api.route('/<int:id>', strict_slashes=False)
class CatResource(Resource):
    @api.doc(security='Bearer Auth')
    @api.marshal_with(cat_model)
    def get(self, id):
        """获取单个猫咪详情"""
        cat = CatService(db).get(id)
        if not cat:
            api.abort(404, '猫咪不存在')
        return cat

    @api.doc(security='Bearer Auth')
    @api.expect(cat_create_model)
    @api.marshal_with(cat_model)
    def put(self, id):
        """更新猫咪信息"""
        data = api.payload
        try:
            current_user_id = current_user.id if current_user.is_authenticated else None
            if current_user_id is None:
                api.abort(401, '需要登录才能更新猫咪信息')
            
            cat = CatService(db).update(
                id,
                current_user_id=current_user_id,
                name=data.get('name'),
                breed=data.get('breed'),
                age=data.get('age'),
                description=data.get('description'),
                is_adopted=data.get('is_adopted'),
                user_id=data.get('user_id', current_user_id),
            )
            if not cat:
                api.abort(404, '猫咪不存在')
            return cat
        except ValueError as e:
            api.abort(400, str(e))
        except Exception as e:
            api.abort(500, str(e))

    @api.doc(security='Bearer Auth')
    def delete(self, id):
        """删除猫咪"""
        try:
            user_id = current_user.id if current_user.is_authenticated else 0
            if CatService(db).delete(id, user_id):
                return '', 204
            api.abort(404, '猫咪不存在')
        except Exception as e:
            api.abort(500, str(e))

@api.route('/search')
class CatSearch(Resource):
    @api.doc(security='Bearer Auth')
    @api.doc(params={
        'q': '搜索关键词',
        'breed': '品种筛选',
        'min_age': '最小年龄',
        'max_age': '最大年龄',
        'is_adopted': '是否被领养(true/false)'
    })
    @api.marshal_list_with(cat_model)
    def get(self):
        """搜索猫咪"""
        search_params = {
            'q': request.args.get('q', ''),
            'breed': request.args.get('breed', ''),
            'min_age': request.args.get('min_age', type=int),
            'max_age': request.args.get('max_age', type=int),
            'is_adopted': request.args.get('is_adopted', type=lambda x: x == 'true')
        }
        cats = CatService(db).search(
            query=search_params['q'],
            breed=search_params['breed'],
            min_age=search_params['min_age'],
            max_age=search_params['max_age'],
            is_adopted=search_params['is_adopted']
        )
        return cats if cats else []
