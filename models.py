"""Модели данных"""
from flask import current_app as app

def init_database():
    """Инициализация базы данных с таблицами"""
    from database import get_db
    
    print("Проверка и создание таблиц базы данных...")
    
    db = get_db()
    
    try:
        # Таблица пользователей
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        
        # Таблица сессий пользователей
        db.execute('''
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
        db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица шаблонов документов
        db.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                doc_type TEXT CHECK(doc_type IN ('Договор', 'Заявление', 'Исковое заявление', 'Соглашение', 'Расторжение', 'Акт', 'Доверенность', 'Приказ', 'Прочее')),
                word_count INTEGER,
                popularity INTEGER DEFAULT 0,
                content_json TEXT,content_json TEXT,
                content_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')
        
        # Таблица полей шаблонов
        db.execute('''
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
        db.execute('''
            CREATE TABLE IF NOT EXISTS filled_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                document_name TEXT NOT NULL,
                document_data TEXT NOT NULL,
                format TEXT DEFAULT 'json',
                status TEXT DEFAULT 'generated',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES templates (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Индексы для ускорения запросов
        db.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_filled_docs_user ON filled_documents(user_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_filled_docs_created ON filled_documents(created_at)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_template_fields_template ON template_fields(template_id)')
        
       # Миграция: добавляем столбцы контента в templates, если их нет
        existing_columns = {
            row['name']
            for row in db.execute("PRAGMA table_info(templates)").fetchall()
        }
        if 'content_json' not in existing_columns:
            db.execute('ALTER TABLE templates ADD COLUMN content_json TEXT')
        if 'content_text' not in existing_columns:
            db.execute('ALTER TABLE templates ADD COLUMN content_text TEXT')

        db.commit()
        print("✓ Таблицы базы данных проверены/созданы")
        
    except Exception as e:
        print(f"✗ Ошибка инициализации базы данных: {e}")
        raise


def cleanup_sessions():
    """Очистка устаревших сессий"""
    from database import get_db
    
    try:
        with app.app_context():
            db = get_db()
            deleted = db.execute('DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP')
            db.commit()
            print(f"✓ Очищено {deleted.rowcount} устаревших сессий")
    except Exception as e:
        print(f"✗ Ошибка очистки сессий: {e}")