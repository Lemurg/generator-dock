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
    
    templates_data = [
        # Договоры
        {
            'name': 'Образец договора аренды квартиры с мебелью и бытовой техникой',
            'category': 'Договоры',
            'type': 'Договор',
            'word_count': 149900,
            'description': 'Полный договор аренды квартиры с мебелью и техникой для длительной аренды',
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
        cursor = conn.execute('''
            INSERT INTO templates (category_id, name, description, doc_type, word_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (category_ids[template['category']], template['name'], 
              template['description'], template['type'], template['word_count']))
        
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