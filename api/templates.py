"""API для работы с шаблонами документов"""

from flask import Blueprint, request, jsonify, Response
import json
from ..models import get_db, get_current_user

templates_bp = Blueprint('templates', __name__)


@templates_bp.route('/api/templates', methods=['GET'])
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


@templates_bp.route('/api/templates/<int:template_id>', methods=['GET'])
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


@templates_bp.route('/api/templates/<int:template_id>/fields', methods=['GET'])
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