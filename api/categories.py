"""API для работы с категориями"""

from flask import Blueprint, jsonify
from ..models import get_db, get_current_user

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/api/categories', methods=['GET'])
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