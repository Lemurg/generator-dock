"""Функции для работы с базой данных"""

import sqlite3
import hashlib
import secrets
import threading
from flask import g, request

DATABASE = 'documents.db'
db_lock = threading.Lock()


def get_db():
    """Получить соединение с базой данных"""
    with db_lock:
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(DATABASE, timeout=30)
            db.row_factory = sqlite3.Row
            # Включаем оптимизации
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = NORMAL")
            db.execute("PRAGMA busy_timeout = 5000")
        return db


def close_connection(exception=None):
    """Закрыть соединение с базой данных"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def hash_password(password):
    """Хеширование пароля с солью"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password, hashed_password):
    """Проверка пароля"""
    if not hashed_password or '$' not in hashed_password:
        return False
    salt, hashed = hashed_password.split('$', 1)
    return hashlib.sha256((password + salt).encode()).hexdigest() == hashed


def get_current_user():
    """Получить текущего пользователя из cookies"""
    user_id = request.cookies.get('user_id')
    token = request.cookies.get('token')
    
    if not user_id or not token:
        return None
    
    try:
        db = get_db()
        session = db.execute(
            '''
            SELECT u.id, u.email, u.username, u.full_name 
            FROM user_sessions s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.user_id = ? 
            AND s.session_token = ? 
            AND s.expires_at > CURRENT_TIMESTAMP 
            AND u.is_active = 1
            ''',
            (user_id, token)
        ).fetchone()
        
        # Обновляем время истечения сессии при каждом обращении
        if session:
            db.execute(
                'UPDATE user_sessions SET expires_at = datetime("now", "+30 days") WHERE user_id = ? AND session_token = ?',
                (user_id, token)
            )
            db.commit()
        
        return session
    except Exception as e:
        print(f"Ошибка получения пользователя: {e}")
        return None