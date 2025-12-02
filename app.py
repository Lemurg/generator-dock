from flask import Flask, jsonify, Response, request, render_template
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """Подключение к базе данных SQLite"""
    conn = sqlite3.connect('documents.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Инициализация базы данных с таблицами"""
    conn = get_db_connection()
    
    # Таблица категорий документов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица шаблонов документов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            doc_type TEXT CHECK(doc_type IN ('Договор', 'Заявление', 'Исковое заявление', 'Соглашение', 'Расторжение', 'Акт', 'Доверенность', 'Приказ', 'Прочее')),
            word_count INTEGER,
            popularity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # Таблица полей шаблонов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS template_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_type TEXT NOT NULL CHECK(field_type IN ('text', 'number', 'date', 'email', 'phone', 'select', 'textarea', 'boolean')),
            is_required BOOLEAN DEFAULT 0,
            min_value INTEGER,
            max_value INTEGER,
            format TEXT,
            placeholder TEXT,
            options TEXT,  -- JSON массив для select полей
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES templates (id)
        )
    ''')
    
    # Таблица заполненных документов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS filled_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            user_id INTEGER,
            document_data TEXT NOT NULL,  -- JSON с заполненными данными
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft',
            FOREIGN KEY (template_id) REFERENCES templates (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# ==================== FRONTEND ROUTES ====================

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/templates')
def templates_page():
    """Страница с шаблонами"""
    return render_template('templates.html')

@app.route('/document/<int:template_id>')
def document_page(template_id):
    """Страница заполнения документа"""
    return render_template('document.html', template_id=template_id)

# ==================== API ROUTES ====================

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Получить все категории документов"""
    try:
        conn = get_db_connection()
        categories = conn.execute('''
            SELECT id, name, description, 
                   (SELECT COUNT(*) FROM templates WHERE category_id = categories.id) as template_count
            FROM categories 
            ORDER BY name
        ''').fetchall()
        conn.close()
        
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
        
        conn = get_db_connection()
        
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
        
        templates = conn.execute(query, params).fetchall()
        conn.close()
        
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
        conn = get_db_connection()
        
        template = conn.execute('''
            SELECT t.*, c.name as category_name 
            FROM templates t 
            LEFT JOIN categories c ON t.category_id = c.id 
            WHERE t.id = ?
        ''', (template_id,)).fetchone()
        
        if not template:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        # Увеличиваем счетчик популярности
        conn.execute('UPDATE templates SET popularity = popularity + 1 WHERE id = ?', (template_id,))
        conn.commit()
        
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
        
        conn.close()
        
        return jsonify({
            'success': True,
            'template': template_data
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/templates/<int:template_id>/fields', methods=['GET'])
def get_template_fields(template_id):
    """Получить поля шаблона"""
    try:
        conn = get_db_connection()
        
        template = conn.execute(
            'SELECT id, name FROM templates WHERE id = ?', 
            (template_id,)
        ).fetchone()
        
        if not template:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        fields = conn.execute('''
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
        conn.close()
        
        response = {
            'success': True,
            'template_id': template_id,
            'template_name': template['name'],
            'fields': []
        }
        
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
            
            response['fields'].append(field_data)
        
        return Response(
            json.dumps(response, ensure_ascii=False, indent=2),
            mimetype='application/json; charset=utf-8'
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/documents/generate', methods=['POST'])
def generate_document():
    """Сгенерировать документ на основе шаблона и данных"""
    try:
        data = request.get_json()
        
        if not data or 'template_id' not in data or 'fields' not in data:
            return jsonify({'error': 'Необходимы template_id и fields'}), 400
        
        template_id = data['template_id']
        fields_data = data['fields']
        
        conn = get_db_connection()
        
        template = conn.execute(
            'SELECT id, name FROM templates WHERE id = ?', 
            (template_id,)
        ).fetchone()
        
        if not template:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        # Валидация полей
        template_fields = conn.execute(
            'SELECT field_key, field_type, is_required FROM template_fields WHERE template_id = ?',
            (template_id,)
        ).fetchall()
        
        required_fields = [field['field_key'] for field in template_fields if field['is_required']]
        for req_field in required_fields:
            if req_field not in fields_data or not fields_data[req_field]:
                return jsonify({'error': f'Обязательное поле "{req_field}" не заполнено'}), 400
        
        # Сохраняем документ
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO filled_documents (template_id, document_data, status)
            VALUES (?, ?, ?)
        ''', (template_id, json.dumps(fields_data), 'generated'))
        
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'message': 'Документ успешно создан',
            'template_name': template['name'],
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка при создании документа: {str(e)}'}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Получить список созданных документов"""
    try:
        conn = get_db_connection()
        
        documents = conn.execute('''
            SELECT fd.id, fd.template_id, fd.created_at, fd.status,
                   t.name as template_name
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            ORDER BY fd.created_at DESC
            LIMIT 100
        ''').fetchall()
        
        conn.close()
        
        documents_list = []
        for doc in documents:
            documents_list.append({
                'id': doc['id'],
                'template_id': doc['template_id'],
                'template_name': doc['template_name'],
                'created_at': doc['created_at'],
                'status': doc['status']
            })
        
        return jsonify({
            'success': True,
            'documents': documents_list,
            'count': len(documents_list)
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Получить статистику по использованию"""
    try:
        conn = get_db_connection()
        
        total_templates = conn.execute('SELECT COUNT(*) as count FROM templates').fetchone()['count']
        total_documents = conn.execute('SELECT COUNT(*) as count FROM filled_documents').fetchone()['count']
        
        popular_templates = conn.execute('''
            SELECT id, name, popularity 
            FROM templates 
            ORDER BY popularity DESC 
            LIMIT 5
        ''').fetchall()
        
        recent_documents = conn.execute('''
            SELECT fd.id, t.name, fd.created_at 
            FROM filled_documents fd
            JOIN templates t ON fd.template_id = t.id
            ORDER BY fd.created_at DESC 
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_templates': total_templates,
                'total_documents': total_documents,
                'popular_templates': [
                    {'id': t['id'], 'name': t['name'], 'popularity': t['popularity']}
                    for t in popular_templates
                ],
                'recent_documents': [
                    {'id': d['id'], 'name': d['name'], 'created_at': d['created_at']}
                    for d in recent_documents
                ]
            }
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/admin/seed', methods=['POST'])
def seed_database():
    """Заполнить базу данных начальными данными"""
    try:
        conn = get_db_connection()
        
        # Очищаем таблицы
        conn.execute('DELETE FROM template_fields')
        conn.execute('DELETE FROM templates')
        conn.execute('DELETE FROM categories')
        
        # Добавляем категории
        categories = [
            ('Договоры', 'Юридические договоры различных типов'),
            ('Заявления', 'Официальные заявления'),
            ('Исковые заявления', 'Документы для подачи в суд'),
            ('Соглашения и расторжения', 'Дополнительные соглашения и расторжения договоров'),
            ('Акты', 'Акты приема-передачи и другие акты'),
            ('Доверенности', 'Доверенности различного назначения'),
            ('Приказы', 'Организационно-распорядительные документы'),
            ('Прочее', 'Прочие документы')
        ]
        
        category_ids = {}
        for name, desc in categories:
            cursor = conn.execute('INSERT INTO categories (name, description) VALUES (?, ?)', (name, desc))
            category_ids[name] = cursor.lastrowid
        
        # 10 КЛЮЧЕВЫХ ШАБЛОНОВ
        templates_data = [
            # 1. Самый популярный - Договор аренды квартиры
            {
                'name': 'Образец договора аренды квартиры с мебелью и бытовой техникой',
                'category': 'Договоры',
                'type': 'Договор',
                'word_count': 149900,
                'description': 'Полный договор аренды квартиры с мебелью и техникой для длительной аренды',
                'fields': [
                    {'key': 'landlord_name', 'label': 'ФИО Арендодателя', 'type': 'text', 'required': True, 'placeholder': 'Иванов Иван Иванович'},
                    {'key': 'landlord_passport', 'label': 'Паспортные данные Арендодателя', 'type': 'text', 'required': True, 'placeholder': 'Серия 1234 №567890 выдан ОВД района'},
                    {'key': 'tenant_name', 'label': 'ФИО Арендатора', 'type': 'text', 'required': True, 'placeholder': 'Петров Петр Петрович'},
                    {'key': 'tenant_passport', 'label': 'Паспортные данные Арендатора', 'type': 'text', 'required': True, 'placeholder': 'Серия 4321 №098765 выдан ОВД района'},
                    {'key': 'address', 'label': 'Адрес квартиры', 'type': 'text', 'required': True, 'placeholder': 'г. Москва, ул. Ленина, д. 1, кв. 1'},
                    {'key': 'apartment_area', 'label': 'Площадь квартиры (кв.м.)', 'type': 'number', 'required': True, 'min': 10, 'max': 500},
                    {'key': 'rooms_count', 'label': 'Количество комнат', 'type': 'number', 'required': True, 'min': 1, 'max': 10},
                    {'key': 'rent_amount', 'label': 'Сумма аренды (руб./мес.)', 'type': 'number', 'required': True, 'min': 1000, 'max': 1000000},
                    {'key': 'start_date', 'label': 'Дата начала аренды', 'type': 'date', 'required': True},
                    {'key': 'end_date', 'label': 'Дата окончания аренды', 'type': 'date', 'required': True},
                    {'key': 'deposit', 'label': 'Залог (руб.)', 'type': 'number', 'required': False, 'min': 0},
                    {'key': 'utilities_included', 'label': 'Коммунальные услуги включены', 'type': 'boolean', 'required': False}
                ]
            },
            
            # 2. Договор купли-продажи авто - очень популярен
            {
                'name': 'Договор купли-продажи транспортного средства',
                'category': 'Договоры',
                'type': 'Договор',
                'word_count': 20017,
                'description': 'Договор купли-продажи автомобиля между физическими лицами',
                'fields': [
                    {'key': 'seller_name', 'label': 'ФИО Продавца', 'type': 'text', 'required': True, 'placeholder': 'Сидоров Алексей Владимирович'},
                    {'key': 'seller_passport', 'label': 'Паспортные данные Продавца', 'type': 'text', 'required': True, 'placeholder': 'Серия 1111 №222222'},
                    {'key': 'buyer_name', 'label': 'ФИО Покупателя', 'type': 'text', 'required': True, 'placeholder': 'Кузнецов Дмитрий Сергеевич'},
                    {'key': 'buyer_passport', 'label': 'Паспортные данные Покупателя', 'type': 'text', 'required': True, 'placeholder': 'Серия 3333 №444444'},
                    {'key': 'car_brand', 'label': 'Марка автомобиля', 'type': 'text', 'required': True, 'placeholder': 'Toyota'},
                    {'key': 'car_model', 'label': 'Модель автомобиля', 'type': 'text', 'required': True, 'placeholder': 'Camry'},
                    {'key': 'car_year', 'label': 'Год выпуска', 'type': 'number', 'required': True, 'min': 1980, 'max': 2024},
                    {'key': 'vin', 'label': 'VIN номер', 'type': 'text', 'required': True, 'placeholder': 'JTDBR32E160123456'},
                    {'key': 'state_number', 'label': 'Государственный номер', 'type': 'text', 'required': True, 'placeholder': 'А123БВ77'},
                    {'key': 'price', 'label': 'Цена (руб.)', 'type': 'number', 'required': True, 'min': 1000, 'max': 10000000},
                    {'key': 'sale_date', 'label': 'Дата продажи', 'type': 'date', 'required': True},
                    {'key': 'payment_method', 'label': 'Способ оплаты', 'type': 'select', 'required': True, 
                     'options': ['Наличные', 'Банковский перевод', 'Другое']}
                ]
            },
            
            # 3. Трудовой договор - базовый документ
            {
                'name': 'Образец трудового договора',
                'category': 'Договоры',
                'type': 'Договор',
                'word_count': 79545,
                'description': 'Стандартный трудовой договор между работодателем и работником',
                'fields': [
                    {'key': 'employer_name', 'label': 'Наименование работодателя', 'type': 'text', 'required': True, 'placeholder': 'ООО "Ромашка"'},
                    {'key': 'employer_details', 'label': 'Реквизиты работодателя', 'type': 'textarea', 'required': True, 'placeholder': 'ИНН 1234567890, ОГРН 1234567890123'},
                    {'key': 'employee_name', 'label': 'ФИО работника', 'type': 'text', 'required': True, 'placeholder': 'Смирнова Анна Петровна'},
                    {'key': 'employee_passport', 'label': 'Паспортные данные работника', 'type': 'text', 'required': True},
                    {'key': 'position', 'label': 'Должность', 'type': 'text', 'required': True, 'placeholder': 'Менеджер по продажам'},
                    {'key': 'department', 'label': 'Отдел/подразделение', 'type': 'text', 'required': True, 'placeholder': 'Отдел продаж'},
                    {'key': 'salary', 'label': 'Оклад (руб.)', 'type': 'number', 'required': True, 'min': 16242, 'max': 1000000},
                    {'key': 'start_date', 'label': 'Дата начала работы', 'type': 'date', 'required': True},
                    {'key': 'contract_type', 'label': 'Вид договора', 'type': 'select', 'required': True,
                     'options': ['Бессрочный', 'Срочный (до 5 лет)', 'Сезонный', 'На время выполнения работы']},
                    {'key': 'probation_period', 'label': 'Испытательный срок (месяцев)', 'type': 'number', 'required': False, 'min': 0, 'max': 6},
                    {'key': 'work_schedule', 'label': 'График работы', 'type': 'select', 'required': True,
                     'options': ['5/2', '6/1', 'Сменный', 'Гибкий']}
                ]
            },
            
            # 4. Заявление на отпуск - самое популярное заявление
            {
                'name': 'Образец заявления на оплачиваемый отпуск',
                'category': 'Заявления',
                'type': 'Заявление',
                'word_count': 15284,
                'description': 'Заявление на ежегодный оплачиваемый отпуск',
                'fields': [
                    {'key': 'to_director', 'label': 'Кому (должность, ФИО)', 'type': 'text', 'required': True, 'placeholder': 'Генеральному директору ООО "Ромашка" Иванову И.И.'},
                    {'key': 'employee_name', 'label': 'От кого (ФИО сотрудника)', 'type': 'text', 'required': True, 'placeholder': 'Петрова Мария Сергеевна'},
                    {'key': 'position', 'label': 'Должность', 'type': 'text', 'required': True, 'placeholder': 'Менеджер'},
                    {'key': 'department', 'label': 'Отдел', 'type': 'text', 'required': True, 'placeholder': 'Отдел маркетинга'},
                    {'key': 'vacation_start', 'label': 'Дата начала отпуска', 'type': 'date', 'required': True},
                    {'key': 'vacation_end', 'label': 'Дата окончания отпуска', 'type': 'date', 'required': True},
                    {'key': 'vacation_days', 'label': 'Количество календарных дней', 'type': 'number', 'required': True, 'min': 1, 'max': 60},
                    {'key': 'vacation_type', 'label': 'Тип отпуска', 'type': 'select', 'required': True,
                     'options': ['Ежегодный оплачиваемый', 'Без сохранения зарплаты', 'Учебный', 'По беременности и родам']},
                    {'key': 'application_date', 'label': 'Дата заявления', 'type': 'date', 'required': True},
                    {'key': 'phone', 'label': 'Контактный телефон', 'type': 'phone', 'required': False, 'placeholder': '+7 (999) 123-45-67'}
                ]
            },
            
            # 5. Договор подряда - популярен для разовых работ
            {
                'name': 'Образец договора подряда, заключаемого между юридическим и физическим лицом',
                'category': 'Договоры',
                'type': 'Договор',
                'word_count': 217729,
                'description': 'Договор подряда на выполнение работ между компанией и физическим лицом',
                'fields': [
                    {'key': 'customer_name', 'label': 'Наименование Заказчика (компания)', 'type': 'text', 'required': True, 'placeholder': 'ООО "СтройГарант"'},
                    {'key': 'customer_details', 'label': 'Реквизиты Заказчика', 'type': 'textarea', 'required': True},
                    {'key': 'contractor_name', 'label': 'ФИО Подрядчика', 'type': 'text', 'required': True},
                    {'key': 'contractor_passport', 'label': 'Паспортные данные Подрядчика', 'type': 'text', 'required': True},
                    {'key': 'work_description', 'label': 'Описание работ', 'type': 'textarea', 'required': True, 'placeholder': 'Ремонт офисного помещения'},
                    {'key': 'work_address', 'label': 'Адрес выполнения работ', 'type': 'text', 'required': True},
                    {'key': 'start_date', 'label': 'Дата начала работ', 'type': 'date', 'required': True},
                    {'key': 'end_date', 'label': 'Дата окончания работ', 'type': 'date', 'required': True},
                    {'key': 'contract_price', 'label': 'Цена договора (руб.)', 'type': 'number', 'required': True, 'min': 1000},
                    {'key': 'advance_payment', 'label': 'Аванс (руб.)', 'type': 'number', 'required': False, 'min': 0},
                    {'key': 'payment_schedule', 'label': 'График платежей', 'type': 'textarea', 'required': False, 'placeholder': '50% - аванс, 50% - после приемки работ'}
                ]
            },
            
            # 6. Исковое заявление о взыскании алиментов
            {
                'name': 'Образец искового заявления о взыскании алиментов на ребенка',
                'category': 'Исковые заявления',
                'type': 'Исковое заявление',
                'word_count': 52892,
                'description': 'Исковое заявление о взыскании алиментов на несовершеннолетнего ребенка',
                'fields': [
                    {'key': 'court_name', 'label': 'Наименование суда', 'type': 'text', 'required': True, 'placeholder': 'Мировой суд судебного участка №1'},
                    {'key': 'plaintiff_name', 'label': 'ФИО Истца (получателя алиментов)', 'type': 'text', 'required': True},
                    {'key': 'plaintiff_address', 'label': 'Адрес Истца', 'type': 'text', 'required': True},
                    {'key': 'plaintiff_phone', 'label': 'Телефон Истца', 'type': 'phone', 'required': True},
                    {'key': 'defendant_name', 'label': 'ФИО Ответчика (плательщика алиментов)', 'type': 'text', 'required': True},
                    {'key': 'defendant_address', 'label': 'Адрес Ответчика', 'type': 'text', 'required': True},
                    {'key': 'child_name', 'label': 'ФИО ребенка', 'type': 'text', 'required': True},
                    {'key': 'child_birthdate', 'label': 'Дата рождения ребенка', 'type': 'date', 'required': True},
                    {'key': 'child_birth_certificate', 'label': 'Свидетельство о рождении', 'type': 'text', 'required': True, 'placeholder': 'серия II-АБ №123456'},
                    {'key': 'marriage_status', 'label': 'Брак зарегистрирован', 'type': 'boolean', 'required': True},
                    {'key': 'alimony_amount', 'label': 'Размер алиментов', 'type': 'select', 'required': True,
                     'options': ['1/4 заработка', '1/3 заработка', '1/2 заработка', 'Твердая денежная сумма']},
                    {'key': 'request', 'label': 'Прошу взыскать', 'type': 'textarea', 'required': True, 
                     'placeholder': 'Взыскать с Ответчика алименты на содержание ребенка...'}
                ]
            },
            
            # 7. Доверенность в налоговую
            {
                'name': 'Образец доверенности в налоговую от юридического лица',
                'category': 'Доверенности',
                'type': 'Доверенность',
                'word_count': 7894,
                'description': 'Доверенность на представление интересов компании в налоговой инспекции',
                'fields': [
                    {'key': 'company_name', 'label': 'Наименование организации', 'type': 'text', 'required': True, 'placeholder': 'ООО "Вектор"'},
                    {'key': 'company_details', 'label': 'Реквизиты организации', 'type': 'textarea', 'required': True, 'placeholder': 'ИНН 1234567890, ОГРН 1234567890123, адрес: г. Москва...'},
                    {'key': 'director_name', 'label': 'ФИО руководителя', 'type': 'text', 'required': True, 'placeholder': 'Генеральный директор Иванов И.И.'},
                    {'key': 'trustee_name', 'label': 'ФИО доверенного лица', 'type': 'text', 'required': True},
                    {'key': 'trustee_passport', 'label': 'Паспортные данные доверенного лица', 'type': 'text', 'required': True},
                    {'key': 'tax_office', 'label': 'Наименование налоговой инспекции', 'type': 'text', 'required': True, 'placeholder': 'ИФНС России №1 по г. Москве'},
                    {'key': 'purpose', 'label': 'Цель доверенности', 'type': 'textarea', 'required': True, 
                     'placeholder': 'Представлять интересы организации, подавать документы, получать документы...'},
                    {'key': 'validity_period', 'label': 'Срок действия (месяцев)', 'type': 'number', 'required': True, 'min': 1, 'max': 36},
                    {'key': 'issue_date', 'label': 'Дата выдачи доверенности', 'type': 'date', 'required': True},
                    {'key': 'with_right_of_substitution', 'label': 'С правом передоверия', 'type': 'boolean', 'required': False}
                ]
            },
            
            # 8. Расторжение договора по соглашению сторон
            {
                'name': 'Образец расторжения договора по соглашению сторон',
                'category': 'Соглашения и расторжения',
                'type': 'Расторжение',
                'word_count': 35118,
                'description': 'Соглашение о расторжении договора по взаимному согласию сторон',
                'fields': [
                    {'key': 'original_contract_number', 'label': 'Номер расторгаемого договора', 'type': 'text', 'required': True, 'placeholder': '№123 от 01.01.2023'},
                    {'key': 'original_contract_date', 'label': 'Дата расторгаемого договора', 'type': 'date', 'required': True},
                    {'key': 'party1_name', 'label': 'Наименование Стороны 1', 'type': 'text', 'required': True},
                    {'key': 'party1_details', 'label': 'Реквизиты Стороны 1', 'type': 'textarea', 'required': True},
                    {'key': 'party2_name', 'label': 'Наименование Стороны 2', 'type': 'text', 'required': True},
                    {'key': 'party2_details', 'label': 'Реквизиты Стороны 2', 'type': 'textarea', 'required': True},
                    {'key': 'termination_date', 'label': 'Дата расторжения договора', 'type': 'date', 'required': True},
                    {'key': 'termination_reason', 'label': 'Причина расторжения', 'type': 'textarea', 'required': True, 
                     'placeholder': 'По взаимному согласию сторон в связи с...'},
                    {'key': 'mutual_settlements', 'label': 'Взаиморасчеты произведены', 'type': 'boolean', 'required': True},
                    {'key': 'no_claims', 'label': 'Стороны претензий друг к другу не имеют', 'type': 'boolean', 'required': True},
                    {'key': 'signature_date', 'label': 'Дата подписания соглашения', 'type': 'date', 'required': True}
                ]
            },
            
            # 9. Акт приема-передачи автомобиля
            {
                'name': 'Образец акта приема-передачи автомобиля (простой)',
                'category': 'Акты',
                'type': 'Акт',
                'word_count': 22754,
                'description': 'Акт приема-передачи транспортного средства',
                'fields': [
                    {'key': 'act_number', 'label': 'Номер акта', 'type': 'text', 'required': True, 'placeholder': 'АКТ-1'},
                    {'key': 'act_date', 'label': 'Дата составления акта', 'type': 'date', 'required': True},
                    {'key': 'transferor_name', 'label': 'ФИО передающего', 'type': 'text', 'required': True},
                    {'key': 'transferee_name', 'label': 'ФИО принимающего', 'type': 'text', 'required': True},
                    {'key': 'car_brand', 'label': 'Марка автомобиля', 'type': 'text', 'required': True},
                    {'key': 'car_model', 'label': 'Модель автомобиля', 'type': 'text', 'required': True},
                    {'key': 'car_year', 'label': 'Год выпуска', 'type': 'number', 'required': True},
                    {'key': 'vin', 'label': 'VIN номер', 'type': 'text', 'required': True},
                    {'key': 'state_number', 'label': 'Государственный номер', 'type': 'text', 'required': True},
                    {'key': 'mileage', 'label': 'Пробег (км)', 'type': 'number', 'required': True, 'min': 0},
                    {'key': 'condition_description', 'label': 'Описание состояния', 'type': 'textarea', 'required': True, 
                     'placeholder': 'Автомобиль передан в исправном техническом состоянии...'},
                    {'key': 'documents_list', 'label': 'Передаваемые документы', 'type': 'textarea', 'required': True,
                     'placeholder': 'ПТС, СТС, ключи (2 шт.), сервисная книжка...'},
                    {'key': 'transfer_purpose', 'label': 'Цель передачи', 'type': 'select', 'required': True,
                     'options': ['Продажа', 'Аренда', 'Хранение', 'Ремонт', 'Другое']}
                ]
            },
            
            # 10. Завещание (прочее)
            {
                'name': 'Образец завещания имущества (с подназначением наследника)',
                'category': 'Прочее',
                'type': 'Прочее',
                'word_count': 3734,
                'description': 'Завещание с указанием основного и подназначенного наследника',
                'fields': [
                    {'key': 'testator_name', 'label': 'ФИО Завещателя', 'type': 'text', 'required': True},
                    {'key': 'testator_passport', 'label': 'Паспортные данные Завещателя', 'type': 'text', 'required': True},
                    {'key': 'testator_address', 'label': 'Адрес Завещателя', 'type': 'text', 'required': True},
                    {'key': 'testator_birthdate', 'label': 'Дата рождения Завещателя', 'type': 'date', 'required': True},
                    {'key': 'notary_name', 'label': 'ФИО нотариуса', 'type': 'text', 'required': True},
                    {'key': 'notary_office', 'label': 'Нотариальная контора', 'type': 'text', 'required': True},
                    {'key': 'main_heir_name', 'label': 'ФИО основного наследника', 'type': 'text', 'required': True},
                    {'key': 'main_heir_relation', 'label': 'Отношение к Завещателю', 'type': 'text', 'required': True, 'placeholder': 'сын, дочь, супруг(а)'},
                    {'key': 'substitute_heir_name', 'label': 'ФИО подназначенного наследника', 'type': 'text', 'required': False},
                    {'key': 'property_description', 'label': 'Описание завещаемого имущества', 'type': 'textarea', 'required': True,
                     'placeholder': 'Квартира, расположенная по адресу... Автомобиль марки... Денежные средства...'},
                    {'key': 'special_conditions', 'label': 'Особые условия', 'type': 'textarea', 'required': False,
                     'placeholder': 'Имущество не подлежит разделу... Наследник обязуется...'},
                    {'key': 'execution_date', 'label': 'Дата составления завещания', 'type': 'date', 'required': True}
                ]
            }
        ]
        
        added_count = 0
        for template in templates_data:
            try:
                cursor = conn.execute('''
                    INSERT INTO templates (category_id, name, description, doc_type, word_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (category_ids[template['category']], template['name'], 
                      template.get('description', ''), template['type'], template['word_count']))
                
                template_id = cursor.lastrowid
                added_count += 1
                
                for i, field in enumerate(template['fields']):
                    options_json = json.dumps(field.get('options', [])) if 'options' in field else None
                    conn.execute('''
                        INSERT INTO template_fields (template_id, field_key, field_label, field_type, 
                                                     is_required, options, placeholder, min_value, max_value, order_index)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (template_id, field['key'], field['label'], field['type'], 
                          field.get('required', False), options_json, field.get('placeholder'),
                          field.get('min'), field.get('max'), i))
                
            except Exception as e:
                print(f"Ошибка при добавлении шаблона '{template['name']}': {str(e)}")
                continue
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'База данных успешно заполнена! Добавлено {added_count} шаблонов.',
            'templates_added': added_count,
            'templates_list': [t['name'] for t in templates_data[:added_count]]
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка при заполнении базы данных: {str(e)}'}), 500
    

if __name__ == '__main__':
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)