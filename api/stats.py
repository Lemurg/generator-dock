"""API для статистики"""

from flask import Blueprint, jsonify
from datetime import datetime
from ..models import get_db, get_current_user
stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Получить статистику для dashboard"""
    try:
        from app import get_current_user
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