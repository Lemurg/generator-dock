"""API для работы с пользователями"""

from flask import Blueprint, request, jsonify
from ..models import get_db, get_current_user

users_bp = Blueprint('users', __name__)


@users_bp.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    """Получить профиль текущего пользователя"""
    try:
        from app import get_current_user
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


@users_bp.route('/api/user/profile', methods=['PUT'])
def update_user_profile():
    """Обновить профиль пользователя"""
    try:
        from app import get_current_user
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных для обновления'}), 400
        
        full_name = data.get('full_name', '').strip()
        
        db = get_db()
        
        try:
            db.execute('BEGIN TRANSACTION')
            
            db.execute('''
                UPDATE users 
                SET full_name = ?
                WHERE id = ?
            ''', (full_name, user['id']))
            
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
            
        except sqlite3.Error as e:
            db.rollback()
            return jsonify({'error': f'Ошибка базы данных: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Ошибка обновления профиля: {str(e)}'}), 500