"""Главный файл приложения Flask"""

from flask import Flask, render_template, redirect, url_for, request, jsonify, Response, g
import atexit
import json
from datetime import datetime
from database import get_db, close_connection, get_current_user, hash_password, verify_password
from models import init_database, cleanup_sessions
from functools import wraps
from word_generator import generate_word_document, generate_contract_document
import urllib.parse
import os
import re

app = Flask(__name__)

# Регистрируем обработчики БД
app.teardown_appcontext(close_connection)


def login_required(f):
    """Декоратор для проверки аутентификации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            # Если это API запрос, возвращаем ошибку
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Требуется аутентификация'}), 401
            # Если это страница, перенаправляем на вход
            return redirect(url_for('auth_page'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== FRONTEND ROUTES ====================

@app.route('/')
def index():
    """Главная страница"""
    user = get_current_user()
    return render_template('index.html', user=user)


@app.route('/templates')
def templates_page():
    """Страница с шаблонами"""
    user = get_current_user()
    return render_template('templates.html', user=user)


@app.route('/document/<int:template_id>')
@login_required
def document_page(template_id):
    """Страница заполнения документа"""
    user = get_current_user()
    return render_template('document.html', template_id=template_id, user=user)


@app.route('/documents')
@login_required
def documents_page():
    """Страница с созданными документами"""
    user = get_current_user()
    return render_template('documents.html', user=user)


@app.route('/auth')
def auth_page():
    """Страница аутентификации"""
    user = get_current_user()
    if user:
        # Если пользователь уже авторизован, перенаправляем на главную
        return redirect(url_for('index'))
    
    return render_template('auth.html', user=user)


@app.route('/profile')
@login_required
def profile_page():
    """Страница профиля пользователя"""
    user = get_current_user()
    return render_template('profile.html', user=user)


@app.route('/stats')
@login_required
def stats_page():
    """Страница статистики"""
    user = get_current_user()
    return render_template('stats.html', user=user)


# ==================== API ROUTES ====================

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Проверить статус аутентификации"""
    try:
        user = get_current_user()
        if user:
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'username': user['username'],
                    'full_name': user['full_name']
                }
            })
        else:
            return jsonify({'authenticated': False})
    except Exception as e:
        return jsonify({'authenticated': False, 'error': str(e)}), 500


@app.route('/api/auth/register', methods=['POST'])
def register_user():
    """Регистрация нового пользователя"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Нет данных'}), 400
            
        email = data.get('email', '').strip().lower()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()
        
        if not email or not username or not password:
            return jsonify({'error': 'Все поля обязательны для заполнения'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
        
        db = get_db()
        
        try:
            db.execute('BEGIN TRANSACTION')
            
            # Проверка существующего email
            existing_user = db.execute(
                'SELECT id FROM users WHERE email = ?', 
                (email,)
            ).fetchone()
            
            if existing_user:
                db.rollback()
                return jsonify({'error': 'Пользователь с таким email уже существует'}), 400
            
            # Хеширование пароля
            password_hash = hash_password(password)
            
            # Создание пользователя
            cursor = db.execute('''
                INSERT INTO users (email, username, password_hash, full_name)
                VALUES (?, ?, ?, ?)
            ''', (email, username, password_hash, full_name))
            
            user_id = cursor.lastrowid
            
            # Создание сессии
            import secrets
            session_token = secrets.token_hex(32)
            db.execute('''
                INSERT INTO user_sessions (user_id, session_token, expires_at)
                VALUES (?, ?, datetime("now", "+30 days"))
            ''', (user_id, session_token))
            
            db.commit()
            
            user_data = db.execute('''
                SELECT id, email, username, full_name FROM users WHERE id = ?
            ''', (user_id,)).fetchone()
            
            response = jsonify({
                'success': True,
                'message': 'Регистрация успешна',
                'user': {
                    'id': user_data['id'],
                    'email': user_data['email'],
                    'username': user_data['username'],
                    'full_name': user_data['full_name']
                }
            })
            
            # Устанавливаем cookies
            response.set_cookie('user_id', str(user_id), max_age=30*24*60*60, httponly=True, samesite='Strict')
            response.set_cookie('token', session_token, max_age=30*24*60*60, httponly=True, samesite='Strict')
            
            return response
            
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка регистрации: {str(e)}'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login_user():
    """Вход пользователя"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Нет данных'}), 400
            
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({'error': 'Email и пароль обязательны'}), 400
        
        db = get_db()
        
        try:
            db.execute('BEGIN TRANSACTION')
            
            # Поиск пользователя
            user = db.execute('''
                SELECT id, email, username, password_hash, full_name 
                FROM users 
                WHERE email = ? AND is_active = 1
            ''', (email,)).fetchone()
            
            if not user:
                db.rollback()
                return jsonify({'error': 'Неверный email или пароль'}), 401
            
            # Проверка пароля
            if not verify_password(password, user['password_hash']):
                db.rollback()
                return jsonify({'error': 'Неверный email или пароль'}), 401
            
            # Создание новой сессии
            import secrets
            session_token = secrets.token_hex(32)
            
            # Удаляем старые сессии
            db.execute('DELETE FROM user_sessions WHERE user_id = ?', (user['id'],))
            
            db.execute('''
                INSERT INTO user_sessions (user_id, session_token, expires_at)
                VALUES (?, ?, datetime("now", "+30 days"))
            ''', (user['id'], session_token))
            
            # Обновляем время последнего входа
            db.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user['id'],))
            
            db.commit()
            
            response = jsonify({
                'success': True,
                'message': 'Вход выполнен успешно',
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'username': user['username'],
                    'full_name': user['full_name']
                }
            })
            
            # Устанавливаем cookies
            response.set_cookie('user_id', str(user['id']), max_age=30*24*60*60, httponly=True, samesite='Strict')
            response.set_cookie('token', session_token, max_age=30*24*60*60, httponly=True, samesite='Strict')
            
            return response
            
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка входа: {str(e)}'}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout_user():
    """Выход пользователя"""
    try:
        user_id = request.cookies.get('user_id')
        token = request.cookies.get('token')
        
        response = jsonify({
            'success': True,
            'message': 'Выход выполнен успешно'
        })
        
        # Удаляем cookies
        response.delete_cookie('user_id')
        response.delete_cookie('token')
        
        # Удаляем сессию из базы данных
        if user_id and token:
            db = get_db()
            try:
                db.execute('DELETE FROM user_sessions WHERE user_id = ? AND session_token = ?', 
                          (user_id, token))
                db.commit()
            except Exception as e:
                print(f"Ошибка удаления сессии: {e}")
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Ошибка выхода: {str(e)}'}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Получить статистику системы"""
    try:
        db = get_db()
        
        stats = db.execute('''
            SELECT 
                (SELECT COUNT(*) FROM templates) as total_templates,
                (SELECT COUNT(*) FROM filled_documents) as total_documents,
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM categories) as total_categories
        ''').fetchone()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_templates': stats['total_templates'],
                'total_documents': stats['total_documents'],
                'total_users': stats['total_users'],
                'total_categories': stats['total_categories']
            }
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Получить все категории документов"""
    try:
        db = get_db()
        categories = db.execute('''
            SELECT id, name, description, 
                   (SELECT COUNT(*) FROM templates WHERE category_id = categories.id) as template_count
            FROM categories 
            ORDER BY name
        ''').fetchall()
        
        categories_list = []
        for cat in categories:
            categories_list.append({
                'id': cat['id'],
                'name': cat['name'],
                'description': cat['description'],
                'template_count': cat['template_count']
            })
        
        return jsonify({
            'success': True,
            'categories': categories_list,
            'count': len(categories_list)
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500


@app.route('/api/templates', methods=['GET'])
def get_all_templates():
    """Получить все шаблоны с фильтрацией"""
    try:
        category_id = request.args.get('category_id', type=int)
        doc_type = request.args.get('doc_type')
        search = request.args.get('search', '')
        
        db = get_db()
        
        query = '''
            SELECT t.id, t.name, t.description, t.doc_type, t.word_count, t.popularity,
                   c.name as category_name
            FROM templates t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE 1=1
        '''
        params = []
        
        if category_id:
            query += ' AND t.category_id = ?'
            params.append(category_id)
        
        if doc_type:
            query += ' AND t.doc_type = ?'
            params.append(doc_type)
        
        if search:
            query += ' AND (t.name LIKE ? OR t.description LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        query += ' ORDER BY t.popularity DESC, t.name'
        
        templates = db.execute(query, params).fetchall()
        
        templates_list = []
        for template in templates:
            templates_list.append({
                'id': template['id'],
                'name': template['name'],
                'description': template['description'],
                'type': template['doc_type'],
                'category': template['category_name'],
                'word_count': template['word_count'],
                'popularity': template['popularity']
            })
        
        return jsonify({
            'success': True,
            'templates': templates_list,
            'count': len(templates_list)
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500


@app.route('/api/templates/<int:template_id>', methods=['GET'])
def get_template_detail(template_id):
    """Получить детальную информацию о шаблоне"""
    try:
        db = get_db()
        
        template = db.execute('''
            SELECT t.*, c.name as category_name 
            FROM templates t 
            LEFT JOIN categories c ON t.category_id = c.id 
            WHERE t.id = ?
        ''', (template_id,)).fetchone()
        
        if not template:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        # Увеличиваем счетчик популярности
        db.execute('UPDATE templates SET popularity = popularity + 1 WHERE id = ?', (template_id,))
        db.commit()
        
        template_data = {
            'id': template['id'],
            'name': template['name'],
            'description': template['description'],
            'type': template['doc_type'],
            'category': template['category_name'],
            'category_id': template['category_id'],
            'word_count': template['word_count'],
            'popularity': template['popularity'],
            'created_at': template['created_at']
        }
        
        return jsonify({
            'success': True,
            'template': template_data
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500


@app.route('/api/templates/<int:template_id>/fields', methods=['GET'])
@login_required
def get_template_fields(template_id):
    """Получить поля шаблона"""
    try:
        db = get_db()
        
        template = db.execute(
            'SELECT id, name FROM templates WHERE id = ?', 
            (template_id,)
        ).fetchone()
        
        if not template:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        fields = db.execute('''
            SELECT 
                field_key, 
                field_label, 
                field_type, 
                is_required,
                min_value,
                max_value,
                format,
                placeholder,
                options,
                order_index
            FROM template_fields 
            WHERE template_id = ? 
            ORDER BY order_index, id
        ''', (template_id,)).fetchall()
        
        response_fields = []
        
        for field in fields:
            field_data = {
                'key': field['field_key'],
                'label': field['field_label'],
                'type': field['field_type'],
                'required': bool(field['is_required']),
                'placeholder': field['placeholder'] or ''
            }
            
            if field['min_value'] is not None:
                field_data['min'] = field['min_value']
            
            if field['max_value'] is not None:
                field_data['max'] = field['max_value']
            
            if field['format'] and field['format'] != '':
                field_data['format'] = field['format']
            
            if field['options']:
                try:
                    field_data['options'] = json.loads(field['options'])
                except:
                    field_data['options'] = []
            
            response_fields.append(field_data)
        
        response_data = {
            'success': True,
            'template_id': template_id,
            'template_name': template['name'],
            'fields': response_fields
        }
        
        return Response(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            mimetype='application/json; charset=utf-8'
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500


@app.route('/api/documents/generate', methods=['POST'])
@login_required
def generate_document():
    """Сгенерировать документ"""
    try:
        data = request.get_json()
        
        if not data or 'template_id' not in data or 'fields' not in data:
            error_data = {'error': 'Необходимы template_id и fields'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 400
        
        template_id = data['template_id']
        fields_data = data['fields']
        document_name = data.get('document_name', '')
        
        user = get_current_user()
        if not user:
            error_data = {'error': 'Требуется аутентификация'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 401
        
        user_id = user['id']
        
        db = get_db()
        
        template = db.execute(
            'SELECT id, name FROM templates WHERE id = ?', 
            (template_id,)
        ).fetchone()
        
        if not template:
            error_data = {'error': 'Шаблон не найден'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 404
        
        # Валидация полей
        template_fields = db.execute(
            'SELECT field_key, field_type, is_required FROM template_fields WHERE template_id = ?',
            (template_id,)
        ).fetchall()
        
        required_fields = [field['field_key'] for field in template_fields if field['is_required']]
        for req_field in required_fields:
            if req_field not in fields_data or not fields_data[req_field]:
                error_data = {'error': f'Обязательное поле "{req_field}" не заполнено'}
                error_response = json.dumps(error_data, ensure_ascii=False)
                return Response(error_response, mimetype='application/json; charset=utf-8'), 400
        
        # Сохраняем документ
        try:
            db.execute('BEGIN TRANSACTION')
            
            if not document_name:
                document_name = f"{template['name']} от {datetime.now().strftime('%d.%m.%Y')}"
            
            cursor = db.execute('''
                INSERT INTO filled_documents (template_id, user_id, document_name, document_data, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (template_id, user_id, document_name, json.dumps(fields_data, ensure_ascii=False), 'generated'))
            
            document_id = cursor.lastrowid
            db.commit()
            
            response_data = {
                'success': True,
                'document_id': document_id,
                'document_name': document_name,
                'message': 'Документ успешно создан',
                'template_name': template['name'],
                'generated_at': datetime.now().isoformat(),
                'view_url': f'/documents/{document_id}',
                'download_url': f'/api/documents/{document_id}/download'
            }
            
            response = json.dumps(response_data, ensure_ascii=False)
            return Response(response, mimetype='application/json; charset=utf-8')
            
        except Exception as e:
            db.rollback()
            error_data = {'error': f'Ошибка базы данных: {str(e)}'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 500
        
    except Exception as e:
        error_data = {'error': f'Ошибка при создании документа: {str(e)}'}
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500


@app.route('/api/documents', methods=['GET'])
@login_required
def get_documents():
    """Получить список созданных документов"""
    try:
        user = get_current_user()
        if not user:
            error_data = {'error': 'Требуется аутентификация'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 401
        
        user_id = user['id']
        
        db = get_db()
        
        # Показываем только документы текущего пользователя
        query = '''
            SELECT fd.id, fd.template_id, fd.document_name, fd.created_at, fd.status,
                   t.name as template_name
            FROM filled_documents fd
            LEFT JOIN templates t ON fd.template_id = t.id
            WHERE fd.user_id = ?
            ORDER BY fd.created_at DESC
            LIMIT 50
        '''
        
        documents = db.execute(query, (user_id,)).fetchall()
        
        documents_list = []
        for doc in documents:
            documents_list.append({
                'id': doc['id'],
                'template_id': doc['template_id'],
                'template_name': doc['template_name'] or 'Неизвестный шаблон',
                'document_name': doc['document_name'] or f"Документ {doc['id']}",
                'created_at': doc['created_at'],
                'status': doc['status'] or 'generated'
            })
        
        response_data = {
            'success': True,
            'documents': documents_list,
            'count': len(documents_list)
        }
        
        response = json.dumps(response_data, ensure_ascii=False)
        return Response(response, mimetype='application/json; charset=utf-8')
        
    except Exception as e:
        error_data = {
            'success': False,
            'error': f'Ошибка сервера: {str(e)}',
            'documents': [],
            'count': 0
        }
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500


@app.route('/api/documents/<int:document_id>', methods=['DELETE'])
@login_required
def delete_document(document_id):
    """Удалить документ"""
    try:
        user = get_current_user()
        if not user:
            error_data = {'error': 'Требуется аутентификация'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 401
        
        db = get_db()
        
        # Проверяем существование документа
        document = db.execute(
            'SELECT id, user_id FROM filled_documents WHERE id = ?', 
            (document_id,)
        ).fetchone()
        
        if not document:
            error_data = {'error': 'Документ не найден'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 404
        
        # Проверяем права доступа (только свои документы)
        if document['user_id'] != user['id']:
            error_data = {'error': 'Нет прав для удаления этого документа'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 403
        
        # Удаляем документ
        try:
            db.execute('BEGIN TRANSACTION')
            db.execute('DELETE FROM filled_documents WHERE id = ?', (document_id,))
            db.commit()
            
            response_data = {
                'success': True,
                'message': 'Документ успешно удален',
                'document_id': document_id
            }
            
            response = json.dumps(response_data, ensure_ascii=False)
            return Response(response, mimetype='application/json; charset=utf-8')
            
        except Exception as e:
            db.rollback()
            error_data = {'error': f'Ошибка базы данных: {str(e)}'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 500
        
    except Exception as e:
        error_data = {'error': f'Ошибка при удалении документа: {str(e)}'}
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500

def create_safe_filename(document_name, doc_id, extension):
    """Создание безопасного ASCII имени файла с правильным расширением"""
    # Преобразуем кириллицу в латиницу (транслитерация)
    def transliterate(text):
        translit_dict = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D',
            'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I',
            'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
            'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
            'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch',
            'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '', 'Ы': 'Y', 'Ь': '',
            'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
        }
        
        result = []
        for char in str(text):
            if char in translit_dict:
                result.append(translit_dict[char])
            elif char.isalnum() or char in '_- ':
                result.append(char)
            else:
                result.append('_')
        
        return ''.join(result)
    
    # Транслитерируем имя документа
    if document_name and document_name.strip():
        safe_name = transliterate(document_name.strip())
    else:
        safe_name = f"document_{doc_id}"
    
    # Заменяем пробелы на подчеркивания
    safe_name = re.sub(r'\s+', '_', safe_name)
    
    # Удаляем все оставшиеся не-ASCII символы
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', safe_name)
    
    # Если имя стало пустым, используем просто document
    if not safe_name:
        safe_name = f"document_{doc_id}"
    
    # Убираем лишние подчеркивания
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_')
    
    # Обрезаем длину
    if len(safe_name) > 40:
        safe_name = safe_name[:40]
    
    # Собираем окончательное имя файла
    filename = f"{safe_name}_{doc_id}.{extension}"
    
    return filename

@app.route('/api/documents/<int:document_id>/download', methods=['GET'])
@login_required
def download_document(document_id):
    """Скачать документ"""
    try:
        format_type = request.args.get('format', 'json').lower()
        
        user = get_current_user()
        if not user:
            error_data = {'error': 'Требуется аутентификация'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 401
        
        db = get_db()
        
        # Ищем документ только текущего пользователя
        documents = db.execute('''
            SELECT fd.*, t.name as template_name, t.description as template_description, c.name as category_name
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE fd.id = ? AND fd.user_id = ?
        ''', (document_id, user['id'])).fetchall()
        
        if not documents:
            error_data = {'error': 'Документ не найден или нет прав доступа'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 404
        
        # Берем первую запись
        document = documents[0]
        
        # Парсим данные документа
        document_data = json.loads(document['document_data'])
        
        if format_type == 'word':
            # Генерация Word документа
            template_data = {
                'id': document['template_id'],
                'name': document['template_name'],
                'description': document['template_description'],
                'category': document['category_name']
            }
            
            user_info = {
                'id': user['id'],
                'username': user['username'],
                'full_name': user['full_name']
            }
            
            word_bytes = generate_word_document(
                template_data=template_data,
                fields_data=document_data,
                document_name=document['document_name'],
                user_info=user_info
            )
            
            # Создаем безопасное имя файла
            filename = create_safe_filename(document['document_name'], document['id'], 'docx')
            
            response = Response(
                word_bytes,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'X-Filename': filename  # Дополнительный заголовок для отладки
                }
            )
            print(f"Скачивание Word: {filename}")  # Для отладки
            return response
        else:
            # Возвращаем JSON
            full_document = {
                'document_id': document['id'],
                'document_name': document['document_name'],
                'template_name': document['template_name'],
                'created_at': document['created_at'],
                'data': document_data,
                'metadata': {
                    'generated_by': 'Document Generator API',
                    'version': '1.0'
                }
            }
            
            # Создаем безопасное имя файла
            filename = create_safe_filename(document['document_name'], document['id'], 'json')
            
            response = Response(
                json.dumps(full_document, ensure_ascii=False, indent=2),
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'application/json; charset=utf-8',
                    'X-Filename': filename  # Дополнительный заголовок для отладки
                }
            )
            print(f"Скачивание JSON: {filename}")  # Для отладки
            return response
        
    except Exception as e:
        error_data = {'error': f'Ошибка сервера: {str(e)}'}
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500


@app.route('/api/documents/<int:document_id>/download/word', methods=['GET'])
@login_required
def download_word_document(document_id):
    """Скачать документ в формате Word"""
    try:
        user = get_current_user()
        if not user:
            error_data = {'error': 'Требуется аутентификация'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 401
        
        db = get_db()
        
        # Ищем документ только текущего пользователя
        document = db.execute('''
            SELECT fd.*, t.name as template_name, t.description as template_description, c.name as category_name
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE fd.id = ? AND fd.user_id = ?
        ''', (document_id, user['id'])).fetchone()
        
        if not document:
            error_data = {'error': 'Документ не найден или нет прав доступа'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 404
        
        # Парсим данные документа
        document_data = json.loads(document['document_data'])
        
        # Подготовка данных для генерации Word
        template_data = {
            'id': document['template_id'],
            'name': document['template_name'],
            'description': document['template_description'],
            'category': document['category_name']
        }
        
        user_info = {
            'id': user['id'],
            'username': user['username'],
            'full_name': user['full_name']
        }
        
        # Генерация Word документа
        word_bytes = generate_word_document(
            template_data=template_data,
            fields_data=document_data,
            document_name=document['document_name'],
            user_info=user_info
        )
        
        # Функция для безопасного создания имени файла
        def safe_filename(filename):
            # Заменяем проблемные символы
            import re
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            # Удаляем лишние пробелы
            filename = filename.strip()
            # Ограничиваем длину
            if len(filename) > 100:
                name, ext = os.path.splitext(filename)
                filename = name[:95] + ext
            return filename
        
        # Создаем безопасное имя файла
        import os
        filename = f"{document['document_name']}_{document['id']}.docx"
        filename = safe_filename(filename)
        
        # Кодируем имя файла для заголовка Content-Disposition
        try:
            # Используем RFC 5987 encoding для UTF-8
            import urllib.parse
            encoded_filename = urllib.parse.quote(filename, encoding='utf-8')
            header_value = f"attachment; filename*=UTF-8''{encoded_filename}"
        except:
            # Если не получается, используем ASCII
            ascii_filename = document['document_name'].encode('ascii', 'ignore').decode('ascii')
            if not ascii_filename:
                ascii_filename = f"document_{document['id']}"
            filename = f"{ascii_filename}_{document['id']}.docx"
            filename = safe_filename(filename)
            header_value = f'attachment; filename="{filename}"'
        
        response = Response(
            word_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={
                'Content-Disposition': header_value,
                'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
        return response
        
    except Exception as e:
        error_data = {'error': f'Ошибка генерации Word документа: {str(e)}'}
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500



@app.route('/api/stats/dashboard', methods=['GET'])
@login_required
def get_dashboard_stats():
    """Получить статистику для dashboard"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        db = get_db()
        
        # Личная статистика пользователя
        user_stats = db.execute('''
            SELECT 
                COUNT(*) as total_documents,
                COUNT(DISTINCT template_id) as unique_templates,
                SUM(CASE WHEN DATE(created_at) = DATE('now') THEN 1 ELSE 0 END) as today_documents,
                SUM(CASE WHEN DATE(created_at) = DATE('now', '-1 day') THEN 1 ELSE 0 END) as yesterday_documents
            FROM filled_documents 
            WHERE user_id = ?
        ''', (user['id'],)).fetchone()
        
        # Последние документы пользователя
        recent_docs = db.execute('''
            SELECT fd.id, fd.document_name, fd.created_at, t.name as template_name
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            WHERE fd.user_id = ?
            ORDER BY fd.created_at DESC
            LIMIT 5
        ''', (user['id'],)).fetchall()
        
        # Популярные шаблоны пользователя
        popular_templates = db.execute('''
            SELECT t.name, COUNT(fd.id) as usage_count
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            WHERE fd.user_id = ?
            GROUP BY t.id
            ORDER BY usage_count DESC
            LIMIT 5
        ''', (user['id'],)).fetchall()
        
        # Глобальная статистика
        global_stats = db.execute('''
            SELECT 
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM templates) as total_templates,
                (SELECT COUNT(*) FROM filled_documents) as total_documents,
                (SELECT COUNT(*) FROM filled_documents WHERE DATE(created_at) = DATE('now')) as today_total_docs
        ''').fetchone()
        
        stats = {
            'user': {
                'total_documents': user_stats['total_documents'] or 0,
                'unique_templates': user_stats['unique_templates'] or 0,
                'today_documents': user_stats['today_documents'] or 0,
                'yesterday_documents': user_stats['yesterday_documents'] or 0,
                'recent_documents': [
                    {
                        'id': doc['id'],
                        'name': doc['document_name'] or f"Документ {doc['id']}",
                        'template': doc['template_name'],
                        'created_at': doc['created_at']
                    } for doc in recent_docs
                ],
                'popular_templates': [
                    {
                        'name': tpl['name'],
                        'usage_count': tpl['usage_count']
                    } for tpl in popular_templates
                ]
            },
            'global': {
                'total_users': global_stats['total_users'],
                'total_templates': global_stats['total_templates'],
                'total_documents': global_stats['total_documents'],
                'today_total_docs': global_stats['today_total_docs'] or 0
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка получения статистики: {str(e)}'}), 500


@app.route('/api/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    """Получить профиль текущего пользователя"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        db = get_db()
        
        # Получаем дополнительную информацию о пользователе
        user_info = db.execute('''
            SELECT created_at, last_login 
            FROM users 
            WHERE id = ?
        ''', (user['id'],)).fetchone()
        
        # Получаем статистику пользователя
        user_stats = db.execute('''
            SELECT 
                COUNT(DISTINCT fd.id) as total_documents,
                COUNT(DISTINCT fd.template_id) as used_templates,
                MIN(fd.created_at) as first_document_date,
                MAX(fd.created_at) as last_document_date
            FROM filled_documents fd
            WHERE fd.user_id = ?
        ''', (user['id'],)).fetchone()
        
        profile_data = {
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'full_name': user['full_name'],
            'created_at': user_info['created_at'],
            'last_login': user_info['last_login'],
            'stats': {
                'total_documents': user_stats['total_documents'] or 0,
                'used_templates': user_stats['used_templates'] or 0,
                'first_document_date': user_stats['first_document_date'],
                'last_document_date': user_stats['last_document_date']
            }
        }
        
        return jsonify({
            'success': True,
            'profile': profile_data
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка получения профиля: {str(e)}'}), 500


@app.route('/api/user/profile', methods=['PUT'])
@login_required
def update_user_profile():
    """Обновить профиль пользователя"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных для обновления'}), 400
        
        full_name = data.get('full_name', '').strip()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        
        if not username or not email:
            return jsonify({'error': 'Имя пользователя и email обязательны'}), 400
        
        db = get_db()
        
        try:
            db.execute('BEGIN TRANSACTION')
            
            # Проверяем, не занят ли email другим пользователем
            if email != user['email']:
                existing_user = db.execute(
                    'SELECT id FROM users WHERE email = ? AND id != ?',
                    (email, user['id'])
                ).fetchone()
                
                if existing_user:
                    db.rollback()
                    return jsonify({'error': 'Этот email уже используется другим пользователем'}), 400
            
            # Проверяем, не занято ли имя пользователя
            if username != user['username']:
                existing_user = db.execute(
                    'SELECT id FROM users WHERE username = ? AND id != ?',
                    (username, user['id'])
                ).fetchone()
                
                if existing_user:
                    db.rollback()
                    return jsonify({'error': 'Это имя пользователя уже занято'}), 400
            
            db.execute('''
                UPDATE users 
                SET full_name = ?, username = ?, email = ?
                WHERE id = ?
            ''', (full_name, username, email, user['id']))
            
            db.commit()
            
            # Получаем обновленные данные
            updated_user = db.execute('''
                SELECT id, email, username, full_name 
                FROM users 
                WHERE id = ?
            ''', (user['id'],)).fetchone()
            
            return jsonify({
                'success': True,
                'message': 'Профиль успешно обновлен',
                'user': {
                    'id': updated_user['id'],
                    'email': updated_user['email'],
                    'username': updated_user['username'],
                    'full_name': updated_user['full_name']
                }
            })
            
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка обновления профиля: {str(e)}'}), 500


@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    """Изменение пароля пользователя"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Требуется текущий и новый пароль'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'Новый пароль должен содержать минимум 6 символов'}), 400
        
        db = get_db()
        
        # Получаем текущий хеш пароля
        user_data = db.execute(
            'SELECT password_hash FROM users WHERE id = ?', 
            (user['id'],)
        ).fetchone()
        
        if not user_data:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        # Проверяем текущий пароль
        if not verify_password(current_password, user_data['password_hash']):
            return jsonify({'error': 'Текущий пароль неверен'}), 401
        
        # Хешируем новый пароль
        new_password_hash = hash_password(new_password)
        
        # Обновляем пароль
        db.execute(
            'UPDATE users SET password_hash = ? WHERE id = ?',
            (new_password_hash, user['id'])
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Пароль успешно изменен'
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка изменения пароля: {str(e)}'}), 500


@app.route('/api/user/delete', methods=['DELETE'])
@login_required
def delete_account():
    """Удаление аккаунта пользователя"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        db = get_db()
        
        try:
            db.execute('BEGIN TRANSACTION')
            
            # Удаляем все сессии пользователя
            db.execute('DELETE FROM user_sessions WHERE user_id = ?', (user['id'],))
            
            # Удаляем все документы пользователя
            db.execute('DELETE FROM filled_documents WHERE user_id = ?', (user['id'],))
            
            # Удаляем пользователя
            db.execute('DELETE FROM users WHERE id = ?', (user['id'],))
            
            db.commit()
            
            response = jsonify({
                'success': True,
                'message': 'Аккаунт успешно удален'
            })
            
            # Удаляем cookies
            response.delete_cookie('user_id')
            response.delete_cookie('token')
            
            return response
            
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка удаления аккаунта: {str(e)}'}), 500


@app.route('/api/documents/<int:document_id>/view', methods=['GET'])
@login_required
def view_document(document_id):
    """Просмотреть документ"""
    try:
        user = get_current_user()
        if not user:
            error_data = {'error': 'Требуется аутентификация'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 401
        
        db = get_db()
        
        # Ищем документ только текущего пользователя
        document = db.execute('''
            SELECT fd.*, t.name as template_name, t.description as template_description
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            WHERE fd.id = ? AND fd.user_id = ?
        ''', (document_id, user['id'])).fetchone()
        
        if not document:
            error_data = {'error': 'Документ не найден или нет прав доступа'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 404
        
        # Парсим данные документа
        document_data = json.loads(document['document_data'])
        
        # Генерируем HTML для просмотра
        html_content = f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{document['document_name']}</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; background-color: #f8f9fa; }}
                .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 2px solid #333; }}
                .document-info {{ margin-bottom: 30px; background: #f5f5f5; padding: 20px; border-radius: 5px; }}
                .field {{ margin-bottom: 20px; }}
                .field-label {{ font-weight: bold; color: #333; margin-bottom: 5px; }}
                .field-value {{ padding: 10px; background: white; border: 1px solid #ddd; border-radius: 3px; min-height: 20px; }}
                .actions {{ margin-top: 40px; text-align: center; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }}
                .btn {{ display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; transition: all 0.3s; }}
                .btn-primary {{ background-color: #4CAF50; color: white; border: none; }}
                .btn-primary:hover {{ background-color: #45a049; }}
                .btn-success {{ background-color: #28a745; color: white; border: none; }}
                .btn-success:hover {{ background-color: #218838; }}
                .btn-secondary {{ background-color: #6c757d; color: white; border: none; }}
                .btn-secondary:hover {{ background-color: #5a6268; }}
                .btn-danger {{ background-color: #dc3545; color: white; border: none; }}
                .btn-danger:hover {{ background-color: #c82333; }}
                .document-meta {{ display: flex; justify-content: space-between; flex-wrap: wrap; margin-bottom: 20px; }}
                .meta-item {{ margin-bottom: 10px; }}
                @media (max-width: 768px) {{
                    .actions {{ flex-direction: column; }}
                    .btn {{ width: 100%; justify-content: center; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{document['document_name']}</h1>
                </div>
                
                <div class="document-meta">
                    <div class="meta-item">
                        <strong>Шаблон:</strong> {document['template_name']}
                    </div>
                    <div class="meta-item">
                        <strong>Создан:</strong> {document['created_at']}
                    </div>
                    <div class="meta-item">
                        <strong>Владелец:</strong> {user['username']}
                    </div>
                </div>
                
                <div class="document-info">
                    <h2>Заполненные данные:</h2>
        '''
        
        # Добавляем каждое поле документа
        for key, value in document_data.items():
            html_content += f'''
                    <div class="field">
                        <div class="field-label">{key}:</div>
                        <div class="field-value">{value}</div>
                    </div>
            '''
        
        html_content += f'''
                </div>
                
                <div class="actions">
                    <a href="/api/documents/{document_id}/download?format=word" class="btn btn-success">
                        <i class="fas fa-file-word"></i> Скачать DOCX
                    </a>
                    <a href="/api/documents/{document_id}/download" class="btn btn-secondary">
                        <i class="fas fa-file-code"></i> Скачать JSON
                    </a>
                    <a href="/documents" class="btn btn-primary">
                        <i class="fas fa-folder-open"></i> Мои документы
                    </a>
                    <a href="/templates" class="btn btn-secondary">
                        <i class="fas fa-file-alt"></i> Шаблоны
                    </a>
                </div>
            </div>
        </body>
        </html>
        '''
        
        return Response(html_content, mimetype='text/html; charset=utf-8')
        
    except Exception as e:
        error_data = {'error': f'Ошибка сервера: {str(e)}'}
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Обработчик 404 ошибки"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Обработчик 500 ошибки"""
    return render_template('500.html'), 500


# ==================== MAIN APPLICATION ====================

if __name__ == '__main__':
    # Инициализация базы данных
    with app.app_context():
        init_database()
        cleanup_sessions()
    
    # Регистрируем очистку сессий при выходе
    atexit.register(cleanup_sessions)
    
    # Запуск приложения
    print("\n" + "="*50)
    print("🚀 Document Generator запущен!")
    print("📁 База данных: documents.db")
    print("🌐 Веб-интерфейс: http://localhost:5000")
    print("🔑 Администратор: test@example.com / test123")
    print("🔑 Обычный пользователь: user@example.com / user123")
    print("📊 Статистика: http://localhost:5000/stats")
    print("👤 Профиль: http://localhost:5000/profile")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)