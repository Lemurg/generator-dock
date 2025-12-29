"""Маршруты для аутентификации"""

from flask import Blueprint, request, jsonify, Response, make_response
import json
import secrets
from models import get_db, hash_password, verify_password

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/check', methods=['GET'])
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


@auth_bp.route('/api/auth/register', methods=['POST'])
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
            
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка регистрации: {str(e)}'}), 500


@auth_bp.route('/api/auth/login', methods=['POST'])
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
            
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка входа: {str(e)}'}), 500


@auth_bp.route('/api/auth/logout', methods=['POST'])
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