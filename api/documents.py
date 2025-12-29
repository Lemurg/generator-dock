"""API для работы с документами"""

from flask import Blueprint, request, jsonify, Response
from flask_login import login_required
import json
from datetime import datetime
from ..models import get_db, get_current_user

documents_bp = Blueprint('documents', __name__)


@documents_bp.route('/api/documents/generate', methods=['POST'])
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
        
        # Получаем текущего пользователя из сессии
        from app import get_current_user
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
            
        except sqlite3.Error as e:
            db.rollback()
            error_data = {'error': f'Ошибка базы данных: {str(e)}'}
            error_response = json.dumps(error_data, ensure_ascii=False)
            return Response(error_response, mimetype='application/json; charset=utf-8'), 500
        
    except Exception as e:
        error_data = {'error': f'Ошибка при создании документа: {str(e)}'}
        error_response = json.dumps(error_data, ensure_ascii=False)
        return Response(error_response, mimetype='application/json; charset=utf-8'), 500


@documents_bp.route('/api/documents', methods=['GET'])
@login_required
def get_documents():
    """Получить список созданных документов"""
    try:
        from app import get_current_user
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