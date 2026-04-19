#rest api для менеджера заметок
#для документации после запуска перейдите по адресу /api/docs
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
from functools import wraps
from models import db, User, Note, Category, Attachment
import os

api_bp = Blueprint('api', __name__, url_prefix='/api')


# конфигурируем jwt
def generate_token(user_id):
    #генерирует jwt токен
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def token_required(f):
    #декоратор для проверки jwt токена

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'error': 'Токен отсутствует или неверный формат'}), 401

        token = token.split(' ')[1]
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = payload['user_id']
            current_user_obj = User.query.get(current_user_id)
            if not current_user_obj:
                return jsonify({'error': 'Пользователь не найден'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Токен истек'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Неверный токен'}), 401

        return f(current_user_obj, *args, **kwargs)

    return decorated


# аутентификация
@api_bp.route('/auth/register', methods=['POST'])
def api_register():
    # регистрация
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Необходимы поля: username, email, password'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Логин уже занят'}), 409

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email уже зарегистрирован'}), 409

    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({
        'message': 'Регистрация успешна',
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    }), 201


@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    #вход в систему и получение jwt токена
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Необходимы поля: username, password'}), 400

    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Неверный логин или пароль'}), 401

    token = generate_token(user.id)
    return jsonify({
        'message': 'Вход выполнен',
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    })


#вспомогательное(функции и все такое)
def note_to_dict(note):
    #преобразует заметку в json
    return {
        'id': note.id,
        'title': note.title,
        'content': note.content,
        'created_at': note.created_at.isoformat(),
        'updated_at': note.updated_at.isoformat(),
        'is_favorite': note.is_favorite,
        'category': {
            'id': note.category.id,
            'name': note.category.name
        } if note.category else None,
        'attachments': [{
            'id': a.id,
            'filename': a.filename,
            'url': f'/uploads/{a.filename}'
        } for a in note.attachments],
        'author': {
            'id': note.author.id,
            'username': note.author.username
        }
    }


# эндпоинты(точки входа) для заметок
@api_bp.route('/notes', methods=['GET'])
@token_required
def api_get_notes(current_user_obj):
    """
    Получить список заметок
    Query params:
    - page: номер страницы (по умолчанию 1)
    - per_page: элементов на странице (по умолчанию 10, макс 50)
    - search: поиск по заголовку/содержимому
    - category_id: фильтр по категории
    - favorites: только избранное (true/false)
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)
    search = request.args.get('search', '')
    category_id = request.args.get('category_id', type=int)
    favorites = request.args.get('favorites', 'false').lower() == 'true'

    query = Note.query.filter_by(user_id=current_user_obj.id)

    if search:
        query = query.filter(
            (Note.title.contains(search)) | (Note.content.contains(search))
        )

    if category_id:
        query = query.filter(Note.category_id == category_id)

    if favorites:
        query = query.filter(Note.is_favorite.is_(True))

    pagination = query.order_by(Note.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'notes': [note_to_dict(n) for n in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


@api_bp.route('/notes/<int:note_id>', methods=['GET'])
@token_required
def api_get_note(current_user_obj, note_id):
    #получает конкретную заметку
    note = Note.query.filter_by(id=note_id, user_id=current_user_obj.id).first()
    if not note:
        return jsonify({'error': 'Заметка не найдена'}), 404

    return jsonify(note_to_dict(note))


@api_bp.route('/notes', methods=['POST'])
@token_required
def api_create_note(current_user_obj):
    #создает новую заметку
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Поле "title" обязательно'}), 400

    note = Note(
        title=data['title'],
        content=data.get('content', ''),
        user_id=current_user_obj.id,
        is_favorite=data.get('is_favorite', False),
        category_id=data.get('category_id') or None
    )

    db.session.add(note)
    db.session.commit()

    return jsonify({
        'message': 'Заметка создана',
        'note': note_to_dict(note)
    }), 201


@api_bp.route('/notes/<int:note_id>', methods=['PUT'])
@token_required
def api_update_note(current_user_obj, note_id):
    #обновляет заметку
    note = Note.query.filter_by(id=note_id, user_id=current_user_obj.id).first()
    if not note:
        return jsonify({'error': 'Заметка не найдена'}), 404

    data = request.get_json()

    if 'title' in data:
        note.title = data['title']
    if 'content' in data:
        note.content = data['content']
    if 'is_favorite' in data:
        note.is_favorite = data['is_favorite']
    if 'category_id' in data:
        note.category_id = data['category_id'] or None

    note.updated_at = datetime.now()
    db.session.commit()

    return jsonify({
        'message': 'Заметка обновлена',
        'note': note_to_dict(note)
    })


@api_bp.route('/notes/<int:note_id>', methods=['DELETE'])
@token_required
def api_delete_note(current_user_obj, note_id):
    #удаляет заметку
    note = Note.query.filter_by(id=note_id, user_id=current_user_obj.id).first()
    if not note:
        return jsonify({'error': 'Заметка не найдена'}), 404

    # удаляет связанные файлы
    for a in note.attachments:
        if os.path.exists(a.file_path):
            os.remove(a.file_path)
        db.session.delete(a)

    db.session.delete(note)
    db.session.commit()

    return jsonify({'message': 'Заметка удалена'})


# категории
@api_bp.route('/categories', methods=['GET'])
@token_required
def api_get_categories(current_user_obj):
    #получает список всех категорий
    categories = Category.query.order_by(Category.name).all()
    return jsonify({
        'categories': [{'id': c.id, 'name': c.name} for c in categories]
    })


# статистика
@api_bp.route('/stats', methods=['GET'])
@token_required
def api_get_stats(current_user_obj):
    # получает статистику по заметкам пользователя
    total_notes = Note.query.filter_by(user_id=current_user_obj.id).count()
    favorite_notes = Note.query.filter_by(user_id=current_user_obj.id, is_favorite=True).count()

    # статистика по категориям
    from sqlalchemy import func
    category_stats = db.session.query(
        Category.name, func.count(Note.id)
    ).outerjoin(Note, (Note.category_id == Category.id) & (Note.user_id == current_user_obj.id)
                ).group_by(Category.id).all()

    return jsonify({
        'total_notes': total_notes,
        'favorite_notes': favorite_notes,
        'categories': [{'name': cat[0], 'count': cat[1]} for cat in category_stats if cat[1] > 0]
    })


# интерактивная документация
@api_bp.route('/docs', methods=['GET'])
def api_docs():
    # документация api
    return jsonify({
        'title': 'Notes Manager API',
        'version': '1.0.0',
        'endpoints': {
            'auth': {
                'POST /api/auth/register': 'Регистрация',
                'POST /api/auth/login': 'Вход (получение токена)'
            },
            'notes': {
                'GET /api/notes': 'Список заметок (с пагинацией и фильтрацией)',
                'GET /api/notes/{id}': 'Получить заметку',
                'POST /api/notes': 'Создать заметку',
                'PUT /api/notes/{id}': 'Обновить заметку',
                'DELETE /api/notes/{id}': 'Удалить заметку'
            },
            'categories': {
                'GET /api/categories': 'Список категорий'
            },
            'stats': {
                'GET /api/stats': 'Статистика пользователя'
            }
        },
        'auth_method': 'Bearer {token} (в заголовке Authorization)'
    })
