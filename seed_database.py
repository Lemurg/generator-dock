#!/usr/bin/env python3
"""
Скрипт для заполнения базы данных тестовыми данными
"""

import sqlite3
import json
import hashlib
import secrets
import os
from datetime import datetime

DATABASE = 'documents.db'

def hash_password(password):
    """Хеширование пароля с солью"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"   

def init_database():
    """Инициализация базы данных с таблицами"""
    print("Создание таблиц базы данных...")
    
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Таблица пользователей
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Таблица сессий пользователей
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
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
            content_json TEXT,
            content_text TEXT,
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
            options TEXT,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE CASCADE
        )
    ''')
    
    # Таблица заполненных документов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS filled_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            user_id INTEGER,
            document_name TEXT,
            document_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft',
            FOREIGN KEY (template_id) REFERENCES templates (id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Таблицы созданы успешно")

def clear_database():
    """Очистка базы данных"""
    print("Очистка базы данных...")
    
    conn = sqlite3.connect(DATABASE)
    
    try:
        # Отключаем внешние ключи для очистки
        conn.execute('PRAGMA foreign_keys = OFF')
        
        # Очищаем таблицы в правильном порядке (с учетом зависимостей)
        conn.execute('DELETE FROM filled_documents')
        conn.execute('DELETE FROM template_fields')
        conn.execute('DELETE FROM templates')
        conn.execute('DELETE FROM categories')
        conn.execute('DELETE FROM user_sessions')
        conn.execute('DELETE FROM users')
        
        # Сбрасываем автоинкремент
        tables = ['filled_documents', 'template_fields', 'templates', 'categories', 'user_sessions', 'users']
        for table in tables:
            try:
                conn.execute(f'DELETE FROM sqlite_sequence WHERE name = ?', (table,))
            except:
                pass
        
        # Включаем внешние ключи обратно
        conn.execute('PRAGMA foreign_keys = ON')
        
        conn.commit()
        print("✓ База данных очищена")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Ошибка очистки базы данных: {e}")
        raise
    finally:
        conn.close()

def seed_users():
    """Заполнение таблицы пользователей"""
    print("Добавление пользователей...")
    
    conn = sqlite3.connect(DATABASE)
    
    users = [
        {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'password123',
            'full_name': 'Тестовый Пользователь'
        },
        {
            'email': 'admin@example.com',
            'username': 'admin',
            'password': 'admin123',
            'full_name': 'Администратор Системы'
        },
        {
            'email': 'user@example.com',
            'username': 'user',
            'password': 'user123',
            'full_name': 'Обычный Пользователь'
        }
    ]
    
    user_ids = {}
    
    for user_data in users:
        password_hash = hash_password(user_data['password'])
        
        cursor = conn.execute('''
            INSERT INTO users (email, username, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', (user_data['email'], user_data['username'], password_hash, user_data['full_name']))
        
        user_id = cursor.lastrowid
        user_ids[user_data['email']] = user_id
        
        # Создаем сессию для тестового пользователя
        if user_data['email'] == 'test@example.com':
            session_token = secrets.token_hex(32)
            conn.execute('''
                INSERT INTO user_sessions (user_id, session_token, expires_at)
                VALUES (?, ?, datetime("now", "+30 days"))
            ''', (user_id, session_token))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Добавлено {len(users)} пользователей")
    return user_ids

def seed_categories():
    """Заполнение таблицы категорий"""
    print("Добавление категорий...")
    
    conn = sqlite3.connect(DATABASE)
    
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
    
    for name, description in categories:
        cursor = conn.execute('INSERT INTO categories (name, description) VALUES (?, ?)', (name, description))
        category_ids[name] = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    print(f"✓ Добавлено {len(categories)} категорий")
    return category_ids

def seed_templates(category_ids):
    """Заполнение таблицы шаблонов"""
    print("Добавление шаблонов документов...")
    
    conn = sqlite3.connect(DATABASE)
    
    def build_content_text(content_blocks):
        lines = []
        for block in content_blocks:
            block_type = block.get('type')
            if block_type == 'list':
                lines.extend([f"- {item}" for item in block.get('items', [])])
            elif block_type == 'signature':
                left_label = block.get('left_label', '')
                right_label = block.get('right_label', '')
                left_name = block.get('left_name', '')
                right_name = block.get('right_name', '')
                lines.append(f"{left_label}: {left_name}".strip())
                lines.append(f"{right_label}: {right_name}".strip())
            elif block_type == 'spacer':
                lines.append("")
            else:
                text = block.get('text', '')
                if text:
                    lines.append(text)
        return "\n".join(lines).strip()

    templates_data = [
        # Договоры
        {
            'name': 'Образец договора аренды квартиры с мебелью и бытовой техникой',
            'category': 'Договоры',
            'type': 'Договор',
            'word_count': 149900,
            'description': 'Полный договор аренды квартиры с мебелью и техникой для длительной аренды',
            'content': [
                {'type': 'title', 'text': 'ДОГОВОР АРЕНДЫ КВАРТИРЫ'},
                {'type': 'paragraph', 'text': 'г. ____________________'},
                {'type': 'paragraph', 'text': '«__» __________ 20__ г.'},
                {'type': 'paragraph', 'text': 'Арендодатель: {landlord_name}, далее именуемый(ая) «Арендодатель», с одной стороны, и Арендатор: {tenant_name}, далее именуемый(ая) «Арендатор», с другой стороны, заключили настоящий договор (далее — «Договор») о нижеследующем.'},
                {'type': 'heading', 'text': '1. Предмет договора'},
                {'type': 'paragraph', 'text': '1.1. Арендодатель передает, а Арендатор принимает во временное владение и пользование жилое помещение, расположенное по адресу: {address} (далее — «Квартира»).'},
                {'type': 'paragraph', 'text': '1.2. Квартира предоставляется для проживания Арендатора и членов его семьи, с соблюдением правил эксплуатации жилых помещений.'},
                {'type': 'paragraph', 'text': '1.3. Перечень мебели и бытовой техники, передаваемых вместе с Квартирой, фиксируется в акте приема-передачи и является неотъемлемой частью Договора.'},
                {'type': 'heading', 'text': '2. Срок аренды'},
                {'type': 'paragraph', 'text': '2.1. Срок аренды устанавливается с {start_date} по {end_date}.'},
                {'type': 'paragraph', 'text': '2.2. Продление срока аренды возможно по соглашению сторон, оформляемому в письменной форме не позднее чем за 10 календарных дней до истечения срока аренды.'},
                {'type': 'heading', 'text': '3. Арендная плата'},
                {'type': 'paragraph', 'text': '3.1. Размер арендной платы составляет {rent_amount} руб. в месяц.'},
                {'type': 'paragraph', 'text': '3.2. Арендная плата вносится ежемесячно не позднее 5-го числа каждого месяца на реквизиты, согласованные сторонами.'},
                {'type': 'paragraph', 'text': '3.3. Коммунальные платежи оплачиваются Арендатором отдельно на основании счетов, выставленных ресурсоснабжающими организациями.'},
                {'type': 'heading', 'text': '4. Права и обязанности сторон'},
                {'type': 'list', 'items': [
                    'Арендодатель обязуется передать Квартиру в состоянии, пригодном для проживания, и обеспечить доступ к инженерным коммуникациям.',
                    'Арендодатель вправе проверять состояние Квартиры по предварительному уведомлению не позднее чем за 24 часа.',
                    'Арендатор обязуется использовать Квартиру исключительно для проживания и соблюдать правила содержания жилого помещения.',
                    'Арендатор обязуется своевременно оплачивать арендную плату и коммунальные услуги.',
                    'Арендатор обязуется бережно относиться к имуществу и не проводить перепланировку без письменного согласия Арендодателя.'
                ]},
                {'type': 'heading', 'text': '5. Ответственность сторон'},
                {'type': 'paragraph', 'text': '5.1. За нарушение сроков оплаты арендной платы Арендатор уплачивает неустойку в размере 0,1% от суммы задолженности за каждый день просрочки.'},
                {'type': 'paragraph', 'text': '5.2. Стороны несут ответственность за неисполнение обязательств по Договору в соответствии с действующим законодательством РФ.'},
                {'type': 'heading', 'text': '6. Заключительные положения'},
                {'type': 'paragraph', 'text': '6.1. Все споры, возникающие из настоящего Договора, решаются путем переговоров, а при недостижении соглашения — в судебном порядке.'},
                {'type': 'paragraph', 'text': '6.2. Договор составлен в двух экземплярах, имеющих одинаковую юридическую силу, по одному для каждой из сторон.'},
                {'type': 'heading', 'text': '7. Подписи сторон'},
                {'type': 'signature', 'left_label': 'Арендодатель', 'right_label': 'Арендатор', 'left_name': '{landlord_name}', 'right_name': '{tenant_name}'}
            ],
            'fields': [
                {'key': 'landlord_name', 'label': 'ФИО Арендодателя', 'type': 'text', 'required': True, 'placeholder': 'Иванов Иван Иванович'},
                {'key': 'tenant_name', 'label': 'ФИО Арендатора', 'type': 'text', 'required': True, 'placeholder': 'Петров Петр Петрович'},
                {'key': 'address', 'label': 'Адрес квартиры', 'type': 'text', 'required': True, 'placeholder': 'г. Москва, ул. Ленина, д. 1, кв. 1'},
                {'key': 'rent_amount', 'label': 'Сумма аренды (руб./мес.)', 'type': 'number', 'required': True, 'min': 1000, 'max': 1000000, 'placeholder': '10000'},
                {'key': 'start_date', 'label': 'Дата начала аренды', 'type': 'date', 'required': True},
                {'key': 'end_date', 'label': 'Дата окончания аренды', 'type': 'date', 'required': True}
            ]
        },
        {
            'name': 'Договор купли-продажи транспортного средства',
            'category': 'Договоры',
            'type': 'Договор',
            'word_count': 20017,
            'description': 'Договор купли-продажи автомобиля между физическими лицами',
            'content': [
                {'type': 'title', 'text': 'ДОГОВОР КУПЛИ-ПРОДАЖИ ТРАНСПОРТНОГО СРЕДСТВА'},
                {'type': 'paragraph', 'text': 'г. ____________________'},
                {'type': 'paragraph', 'text': '«__» __________ 20__ г.'},
                {'type': 'paragraph', 'text': 'Продавец: {seller_name}, и Покупатель: {buyer_name}, заключили настоящий договор (далее — «Договор») о нижеследующем.'},
                {'type': 'heading', 'text': '1. Предмет договора'},
                {'type': 'paragraph', 'text': '1.1. Продавец передает в собственность, а Покупатель принимает автомобиль {car_brand} {car_model}, год выпуска {car_year} (далее — «Автомобиль»).'},
                {'type': 'paragraph', 'text': '1.2. Автомобиль передается в исправном состоянии, соответствует техническим требованиям и находится в собственности Продавца.'},
                {'type': 'heading', 'text': '2. Цена и порядок расчетов'},
                {'type': 'paragraph', 'text': '2.1. Цена Автомобиля составляет {price} руб.'},
                {'type': 'paragraph', 'text': '2.2. Оплата производится в полном объеме в момент подписания Договора наличными либо путем перечисления на банковские реквизиты Продавца.'},
                {'type': 'paragraph', 'text': '2.3. Факт оплаты подтверждается распиской Продавца.'},
                {'type': 'heading', 'text': '3. Переход права собственности'},
                {'type': 'paragraph', 'text': '3.1. Право собственности на Автомобиль переходит к Покупателю после подписания Договора и передачи Автомобиля вместе с комплектом ключей и документами.'},
                {'type': 'heading', 'text': '4. Права и обязанности сторон'},
                {'type': 'list', 'items': [
                    'Продавец обязуется передать Автомобиль в согласованный срок и предоставить необходимые документы (ПТС, СТС).',
                    'Покупатель обязуется принять Автомобиль и оплатить его стоимость в полном объеме.',
                    'Стороны подтверждают отсутствие взаимных претензий после передачи Автомобиля.'
                ]},
                {'type': 'heading', 'text': '5. Заключительные положения'},
                {'type': 'paragraph', 'text': '5.1. Договор составлен в двух экземплярах, имеющих одинаковую юридическую силу, по одному для каждой из сторон.'},
                {'type': 'heading', 'text': '6. Подписи сторон'},
                {'type': 'signature', 'left_label': 'Продавец', 'right_label': 'Покупатель', 'left_name': '{seller_name}', 'right_name': '{buyer_name}'}
            ],
            'fields': [
                {'key': 'seller_name', 'label': 'ФИО Продавца', 'type': 'text', 'required': True, 'placeholder': 'Сидоров Алексей Владимирович'},
                {'key': 'buyer_name', 'label': 'ФИО Покупателя', 'type': 'text', 'required': True, 'placeholder': 'Кузнецов Дмитрий Сергеевич'},
                {'key': 'car_brand', 'label': 'Марка автомобиля', 'type': 'text', 'required': True, 'placeholder': 'Toyota'},
                {'key': 'car_model', 'label': 'Модель автомобиля', 'type': 'text', 'required': True, 'placeholder': 'Camry'},
                {'key': 'car_year', 'label': 'Год выпуска', 'type': 'number', 'required': True, 'min': 1980, 'max': 2024},
                {'key': 'price', 'label': 'Цена (руб.)', 'type': 'number', 'required': True, 'min': 1000, 'max': 10000000, 'placeholder': '500000'}
            ]
        },
        # Заявления
        {
            'name': 'Образец заявления на оплачиваемый отпуск',
            'category': 'Заявления',
            'type': 'Заявление',
            'word_count': 15284,
            'description': 'Заявление на ежегодный оплачиваемый отпуск',
            'content': [
                {'type': 'paragraph', 'text': 'Кому: {to_director}'},
                {'type': 'paragraph', 'text': 'От: {employee_name}, должность {position}'},
                {'type': 'spacer'},
                {'type': 'title', 'text': 'ЗАЯВЛЕНИЕ'},
                {'type': 'paragraph', 'text': 'Прошу предоставить мне {vacation_type} отпуск сроком {vacation_days} календарных дней с {vacation_start}.'},
                {'type': 'spacer'},
                {'type': 'paragraph', 'text': 'Дата: ____________________'},
                {'type': 'paragraph', 'text': 'Подпись: ____________________ {employee_name}'}
            ],
            'fields': [
                {'key': 'to_director', 'label': 'Кому (должность, ФИО)', 'type': 'text', 'required': True, 'placeholder': 'Генеральному директору ООО "Ромашка" Иванову И.И.'},
                {'key': 'employee_name', 'label': 'От кого (ФИО сотрудника)', 'type': 'text', 'required': True, 'placeholder': 'Петрова Мария Сергеевна'},
                {'key': 'position', 'label': 'Должность', 'type': 'text', 'required': True, 'placeholder': 'Менеджер'},
                {'key': 'vacation_start', 'label': 'Дата начала отпуска', 'type': 'date', 'required': True},
                {'key': 'vacation_days', 'label': 'Количество календарных дней', 'type': 'number', 'required': True, 'min': 1, 'max': 60},
                {'key': 'vacation_type', 'label': 'Тип отпуска', 'type': 'select', 'required': True, 'options': ['Ежегодный оплачиваемый', 'Без сохранения зарплаты', 'Учебный', 'По беременности и родам']}
            ]
        },
        # Исковые заявления
        {
            'name': 'Образец искового заявления о взыскании алиментов на ребенка',
            'category': 'Исковые заявления',
            'type': 'Исковое заявление',
            'word_count': 52892,
            'description': 'Исковое заявление о взыскании алиментов на несовершеннолетнего ребенка',
            'content': [
                {'type': 'paragraph', 'text': 'В {court_name}'},
                {'type': 'paragraph', 'text': 'Истец: {plaintiff_name}'},
                {'type': 'paragraph', 'text': 'Ответчик: {defendant_name}'},
                {'type': 'spacer'},
                {'type': 'title', 'text': 'ИСКОВОЕ ЗАЯВЛЕНИЕ'},
                {'type': 'paragraph', 'text': 'Я, {plaintiff_name}, являюсь родителем несовершеннолетнего ребенка {child_name}, дата рождения {child_birthdate}.'},
                {'type': 'paragraph', 'text': 'Ответчик {defendant_name} обязан(а) содержать ребенка, однако добровольно материальной помощи не оказывает.'},
                {'type': 'paragraph', 'text': 'На основании статей 80–83 Семейного кодекса РФ прошу взыскать алименты на содержание ребенка в размере {alimony_amount}.'},
                {'type': 'spacer'},
                {'type': 'paragraph', 'text': 'Приложения:'},
                {'type': 'list', 'items': [
                    'Копия свидетельства о рождении ребенка.',
                    'Копии документов, подтверждающих расходы на содержание ребенка.',
                    'Копия искового заявления для ответчика.'
                ]},
                {'type': 'spacer'},
                {'type': 'paragraph', 'text': 'Дата: ____________________'},
                {'type': 'paragraph', 'text': 'Подпись: ____________________ {plaintiff_name}'}
            ],
            'fields': [
                {'key': 'court_name', 'label': 'Наименование суда', 'type': 'text', 'required': True, 'placeholder': 'Мировой суд судебного участка №1'},
                {'key': 'plaintiff_name', 'label': 'ФИО Истца (получателя алиментов)', 'type': 'text', 'required': True},
                {'key': 'defendant_name', 'label': 'ФИО Ответчика (плательщика алиментов)', 'type': 'text', 'required': True},
                {'key': 'child_name', 'label': 'ФИО ребенка', 'type': 'text', 'required': True},
                {'key': 'child_birthdate', 'label': 'Дата рождения ребенка', 'type': 'date', 'required': True},
                {'key': 'alimony_amount', 'label': 'Размер алиментов', 'type': 'select', 'required': True, 'options': ['1/4 заработка', '1/3 заработка', '1/2 заработка', 'Твердая денежная сумма']}
            ]
        },
        # Доверенности
        {
            'name': 'Образец доверенности в налоговую от юридического лица',
            'category': 'Доверенности',
            'type': 'Доверенность',
            'word_count': 7894,
            'description': 'Доверенность на представление интересов компании в налоговой инспекции',
            'content': [
                {'type': 'title', 'text': 'ДОВЕРЕННОСТЬ'},
                {'type': 'paragraph', 'text': 'г. ____________________'},
                {'type': 'paragraph', 'text': '«__» __________ 20__ г.'},
                {'type': 'paragraph', 'text': '{company_name} в лице {director_name} настоящей доверенностью уполномочивает {trustee_name} представлять интересы организации в {tax_office}.'},
                {'type': 'paragraph', 'text': 'Полномочия включают подачу документов, получение справок и представление интересов в рамках компетенции налогового органа.'},
                {'type': 'paragraph', 'text': 'Срок действия доверенности: {validity_period} месяцев.'},
                {'type': 'paragraph', 'text': 'Доверенность выдана без права передоверия, если иное не указано письменно.'},
                {'type': 'heading', 'text': 'Подписи'},
                {'type': 'signature', 'left_label': 'Доверитель', 'right_label': 'Доверенное лицо', 'left_name': '{director_name}', 'right_name': '{trustee_name}'}
            ],
            'fields': [
                {'key': 'company_name', 'label': 'Наименование организации', 'type': 'text', 'required': True, 'placeholder': 'ООО "Вектор"'},
                {'key': 'director_name', 'label': 'ФИО руководителя', 'type': 'text', 'required': True, 'placeholder': 'Генеральный директор Иванов И.И.'},
                {'key': 'trustee_name', 'label': 'ФИО доверенного лица', 'type': 'text', 'required': True},
                {'key': 'tax_office', 'label': 'Наименование налоговой инспекции', 'type': 'text', 'required': True, 'placeholder': 'ИФНС России №1 по г. Москве'},
                {'key': 'validity_period', 'label': 'Срок действия (месяцев)', 'type': 'number', 'required': True, 'min': 1, 'max': 36}
            ]
        }
    ]
    
    template_ids = {}
    
    for template in templates_data:
        content_blocks = template.get('content', [])
        content_json = json.dumps(content_blocks, ensure_ascii=False)
        content_text = build_content_text(content_blocks)
        cursor = conn.execute('''
            INSERT INTO templates (category_id, name, description, doc_type, word_count, content_json, content_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (category_ids[template['category']], template['name'],
              template['description'], template['type'], template['word_count'], content_json, content_text))
        
        template_id = cursor.lastrowid
        template_ids[template['name']] = template_id
        
        # Добавляем поля шаблона
        for i, field in enumerate(template['fields']):
            options_json = json.dumps(field.get('options', [])) if 'options' in field else None
            conn.execute('''
                INSERT INTO template_fields (template_id, field_key, field_label, field_type, 
                                             is_required, options, placeholder, min_value, max_value, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, field['key'], field['label'], field['type'], 
                  field.get('required', False), options_json, field.get('placeholder'),
                  field.get('min'), field.get('max'), i))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Добавлено {len(templates_data)} шаблонов")
    return template_ids

def seed_documents(user_ids, template_ids):
    """Заполнение таблицы созданных документов"""
    print("Добавление тестовых документов...")
    
    conn = sqlite3.connect(DATABASE)
    
    # Получаем ID тестового пользователя
    test_user_id = user_ids.get('test@example.com')
    
    if not test_user_id:
        print("✗ Не найден тестовый пользователь")
        return
    
    # Получаем первый шаблон
    first_template_id = list(template_ids.values())[0] if template_ids else None
    
    if not first_template_id:
        print("✗ Нет доступных шаблонов")
        return
    
    # Создаем несколько тестовых документов
    documents = [
        {
            'template_id': first_template_id,
            'user_id': test_user_id,
            'document_name': 'Договор аренды квартиры от 15.12.2024',
            'document_data': {
                'landlord_name': 'Иванов Иван Иванович',
                'tenant_name': 'Петров Петр Петрович',
                'address': 'г. Москва, ул. Ленина, д. 1, кв. 1',
                'rent_amount': '25000',
                'start_date': '2024-12-15',
                'end_date': '2025-12-14'
            }
        },
        {
            'template_id': first_template_id,
            'user_id': test_user_id,
            'document_name': 'Договор аренды офиса от 01.01.2025',
            'document_data': {
                'landlord_name': 'Сидоров Сергей Сергеевич',
                'tenant_name': 'Кузнецов Константин Константинович',
                'address': 'г. Москва, ул. Пушкина, д. 10, офис 25',
                'rent_amount': '50000',
                'start_date': '2025-01-01',
                'end_date': '2025-12-31'
            }
        }
    ]
    
    for doc in documents:
        conn.execute('''
            INSERT INTO filled_documents (template_id, user_id, document_name, document_data, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (doc['template_id'], doc['user_id'], doc['document_name'], 
              json.dumps(doc['document_data'], ensure_ascii=False), 'generated'))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Добавлено {len(documents)} тестовых документов")

def show_summary():
    """Показать сводку по заполненным данным"""
    print("\n" + "="*50)
    print("СВОДКА ПО БАЗЕ ДАННЫХ")
    print("="*50)
    
    conn = sqlite3.connect(DATABASE)
    
    # Пользователи
    users_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()[0]
    print(f"👥 Пользователей: {users_count}")
    
    users = conn.execute('SELECT email, username FROM users').fetchall()
    for user in users:
        print(f"   - {user[1]} ({user[0]})")
    
    # Категории
    categories_count = conn.execute('SELECT COUNT(*) as count FROM categories').fetchone()[0]
    print(f"\n📁 Категорий: {categories_count}")
    
    # Шаблоны
    templates_count = conn.execute('SELECT COUNT(*) as count FROM templates').fetchone()[0]
    print(f"📄 Шаблонов: {templates_count}")
    
    # Документы
    documents_count = conn.execute('SELECT COUNT(*) as count FROM filled_documents').fetchone()[0]
    print(f"📝 Документов: {documents_count}")
    
    conn.close()
    
    print("\n" + "="*50)
    print("ДЛЯ ТЕСТИРОВАНИЯ ИСПОЛЬЗУЙТЕ:")
    print("="*50)
    print("1. test@example.com / password123")
    print("2. admin@example.com / admin123")
    print("3. user@example.com / user123")
    print("\nДля запуска сервера выполните: python app.py")
    print("Затем откройте: http://localhost:5000")

def main():
    """Основная функция"""
    print("="*50)
    print("ЗАПОЛНЕНИЕ БАЗЫ ДАННЫХ ТЕСТОВЫМИ ДАННЫМИ")
    print("="*50)
    
    # Проверяем, существует ли база данных
    if os.path.exists(DATABASE):
        response = input(f"\nБаза данных '{DATABASE}' уже существует.\nОчистить и перезаписать? (y/N): ")
        if response.lower() != 'y':
            print("Операция отменена.")
            return
        clear_database()
    else:
        print("Создание новой базы данных...")
        init_database()
    
    try:
        # Заполняем базу данных
        init_database()
        user_ids = seed_users()
        category_ids = seed_categories()
        template_ids = seed_templates(category_ids)
        seed_documents(user_ids, template_ids)
        
        show_summary()
        
        print("\n" + "="*50)
        print("✓ База данных успешно заполнена!")
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ Ошибка при заполнении базы данных: {e}")
        print("Попробуйте удалить файл documents.db и запустить скрипт заново")

if __name__ == '__main__':
    main()