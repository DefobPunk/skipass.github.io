"""
🎿 Система продажи ски-пассов
Запуск: python ski_pass_app.py
Открыть: http://localhost:5000
Логин: admin / admin123
"""

import os
import random
import re
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, flash, jsonify, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "ski-pass-secret-key-2024")
app.config['TEMPLATES_AUTO_RELOAD'] = True

def get_db_connection():
    try:
        connection = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "ski_resort"),
            port=int(os.getenv("DB_PORT", "3306")),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

def init_database():
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # Таблица пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    login VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(200) NOT NULL,
                    phone VARCHAR(20) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    role_id INT UNSIGNED DEFAULT 1,
                    is_active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_users_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Таблица ролей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    description VARCHAR(200)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Добавляем стандартные роли
            cursor.execute("INSERT IGNORE INTO roles (id, name, description) VALUES (1, 'user', 'Обычный пользователь')")
            cursor.execute("INSERT IGNORE INTO roles (id, name, description) VALUES (2, 'admin', 'Администратор системы')")
            cursor.execute("INSERT IGNORE INTO roles (id, name, description) VALUES (3, 'cashier', 'Кассир')")
            
            # Таблица курортов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resorts (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    location VARCHAR(200) NOT NULL,
                    description TEXT,
                    slopes_count INT DEFAULT 0,
                    lifts_count INT DEFAULT 0,
                    is_active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Таблица типов ски-пассов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pass_types (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    duration_days INT NOT NULL,
                    price DECIMAL(10, 2) NOT NULL,
                    is_active TINYINT(1) DEFAULT 1,
                    resort_id INT UNSIGNED,
                    FOREIGN KEY (resort_id) REFERENCES resorts(id) ON DELETE SET NULL,
                    INDEX idx_pass_types_resort (resort_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Таблица продаж ски-пассов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pass_sales (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    customer_name VARCHAR(200) NOT NULL,
                    customer_email VARCHAR(255),
                    customer_phone VARCHAR(20),
                    pass_type_id INT UNSIGNED NOT NULL,
                    resort_id INT UNSIGNED NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    total_amount DECIMAL(10, 2) NOT NULL,
                    sale_date DATE NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status VARCHAR(20) DEFAULT 'paid',
                    payment_method VARCHAR(50) DEFAULT 'online',
                    sold_by BIGINT UNSIGNED DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pass_type_id) REFERENCES pass_types(id) ON DELETE CASCADE,
                    FOREIGN KEY (resort_id) REFERENCES resorts(id) ON DELETE CASCADE,
                    FOREIGN KEY (sold_by) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_sales_date (sale_date),
                    INDEX idx_sales_resort (resort_id),
                    INDEX idx_sales_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Таблица подъемников
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lifts (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    resort_id INT UNSIGNED NOT NULL,
                    lift_type VARCHAR(50) NOT NULL,
                    capacity INT DEFAULT 4,
                    status VARCHAR(20) DEFAULT 'operational',
                    last_maintenance DATE,
                    FOREIGN KEY (resort_id) REFERENCES resorts(id) ON DELETE CASCADE,
                    INDEX idx_lifts_resort (resort_id),
                    INDEX idx_lifts_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Таблица снежных условий
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snow_conditions (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    resort_id INT UNSIGNED NOT NULL,
                    date DATE NOT NULL,
                    snow_depth_cm INT DEFAULT 0,
                    new_snow_cm INT DEFAULT 0,
                    temperature_min INT DEFAULT -5,
                    temperature_max INT DEFAULT 0,
                    weather_condition VARCHAR(50) DEFAULT 'sunny',
                    FOREIGN KEY (resort_id) REFERENCES resorts(id) ON DELETE CASCADE,
                    UNIQUE KEY idx_resort_date (resort_id, date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Создаем администратора если его нет
            cursor.execute("SELECT id FROM users WHERE login = 'admin'")
            admin_exists = cursor.fetchone()
            
            if not admin_exists:
                password_hash = generate_password_hash('admin123')
                cursor.execute("""
                    INSERT INTO users (login, password_hash, full_name, phone, email, role_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, ('admin', password_hash, 'Администратор Системы', '8(999)123-45-67', 'admin@ski-resort.com', 2, 1))
            
            # Добавляем тестовые курорты если их нет
            cursor.execute("SELECT COUNT(*) as count FROM resorts")
            resorts_count = cursor.fetchone()['count']
            
            if resorts_count == 0:
                test_resorts = [
                    ('Горный Пик', 'Кавказские горы', 'Крупнейший горнолыжный курорт с трассами для всех уровней', 25, 12),
                    ('Снежная Долина', 'Алтай', 'Семейный курорт с живописными видами', 15, 8),
                    ('Ледяной Ветер', 'Урал', 'Экстремальный курорт для профессионалов', 10, 6),
                    ('Зимняя Сказка', 'Кольский полуостров', 'Курорт с длинным сезоном и стабильным снегом', 20, 10),
                ]
                
                for resort in test_resorts:
                    cursor.execute("""
                        INSERT INTO resorts (name, location, description, slopes_count, lifts_count)
                        VALUES (%s, %s, %s, %s, %s)
                    """, resort)
            
            # Добавляем типы ски-пассов
            cursor.execute("SELECT COUNT(*) as count FROM pass_types")
            passes_count = cursor.fetchone()['count']
            
            if passes_count == 0:
                cursor.execute("SELECT id FROM resorts LIMIT 4")
                resort_ids = [row['id'] for row in cursor.fetchall()]
                
                pass_types_data = []
                for resort_id in resort_ids:
                    pass_types_data.extend([
                        ('1-дневный', 'Разовый подъем на все подъемники', 1, 2500.00, resort_id),
                        ('3-дневный', 'Трехдневный безлимит', 3, 6500.00, resort_id),
                        ('5-дневный', 'Пятидневный абонемент', 5, 9500.00, resort_id),
                        ('Сезонный', 'Безлимит на весь сезон', 180, 35000.00, resort_id),
                        ('Детский 1-день', 'Для детей до 12 лет', 1, 1500.00, resort_id),
                    ])
                
                for pass_type in pass_types_data:
                    cursor.execute("""
                        INSERT INTO pass_types (name, description, duration_days, price, resort_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """, pass_type)
            
            # Добавляем подъемники
            cursor.execute("SELECT COUNT(*) as count FROM lifts")
            lifts_count = cursor.fetchone()['count']
            
            if lifts_count == 0:
                cursor.execute("SELECT id FROM resorts")
                resorts = cursor.fetchall()
                
                lift_types = ['кресельный', 'бугельный', 'кабинный', 'ленточный']
                
                for resort in resorts:
                    for i in range(1, 5):
                        lift_name = f"Подъемник {i}"
                        lift_type = random.choice(lift_types)
                        capacity = random.choice([2, 4, 6, 8])
                        status = random.choice(['operational', 'operational', 'maintenance', 'operational'])
                        
                        cursor.execute("""
                            INSERT INTO lifts (name, resort_id, lift_type, capacity, status)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (lift_name, resort['id'], lift_type, capacity, status))
            
            # Генерируем снежные условия
            cursor.execute("SELECT COUNT(*) as count FROM snow_conditions")
            snow_count = cursor.fetchone()['count']
            
            if snow_count == 0:
                cursor.execute("SELECT id FROM resorts")
                resorts = cursor.fetchall()
                weather_conditions = ['sunny', 'cloudy', 'snow', 'blizzard', 'fog']
                
                for resort in resorts:
                    for days_ago in range(30):
                        date = (datetime.now() - timedelta(days=days_ago)).date()
                        snow_depth = random.randint(50, 200)
                        new_snow = random.randint(0, 30)
                        temp_min = random.randint(-15, -5)
                        temp_max = random.randint(-5, 5)
                        weather = random.choice(weather_conditions)
                        
                        cursor.execute("""
                            INSERT INTO snow_conditions (resort_id, date, snow_depth_cm, new_snow_cm, temperature_min, temperature_max, weather_condition)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (resort['id'], date, snow_depth, new_snow, temp_min, temp_max, weather))
            
            # Генерируем тестовые продажи
            cursor.execute("SELECT COUNT(*) as count FROM pass_sales")
            sales_count = cursor.fetchone()['count']
            
            if sales_count == 0:
                cursor.execute("SELECT id FROM pass_types")
                pass_types = cursor.fetchall()
                
                cursor.execute("SELECT id FROM resorts")
                resorts = cursor.fetchall()
                
                customer_names = ['Иванов Иван', 'Петрова Мария', 'Сидоров Алексей', 'Кузнецова Анна', 'Смирнов Дмитрий']
                payment_methods = ['online', 'cash', 'card', 'terminal']
                statuses = ['paid', 'paid', 'paid', 'pending', 'cancelled']
                
                for i in range(200):
                    sale_date = datetime.now() - timedelta(days=random.randint(0, 60))
                    start_date = sale_date + timedelta(days=random.randint(0, 7))
                    
                    pass_type = random.choice(pass_types)
                    resort = random.choice(resorts)
                    
                    quantity = random.randint(1, 4)
                    total = quantity * pass_type['price'] * (0.9 + random.random() * 0.2)  # Случайная скидка
                    end_date = start_date + timedelta(days=pass_type['duration_days'])
                    
                    cursor.execute("""
                        INSERT INTO pass_sales (
                            customer_name, customer_email, customer_phone,
                            pass_type_id, resort_id, quantity, total_amount,
                            sale_date, start_date, end_date, status, payment_method
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        random.choice(customer_names),
                        f"customer{i}@example.com",
                        f"8(999){random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}",
                        pass_type['id'],
                        resort['id'],
                        quantity,
                        round(total, 2),
                        sale_date.date(),
                        start_date.date(),
                        end_date.date(),
                        random.choice(statuses),
                        random.choice(payment_methods)
                    ))
            
            conn.commit()
            print("✅ База данных инициализирована успешно!")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# Базовый шаблон HTML
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        .navbar {
            background: rgba(255, 255, 255, 0.95);
            color: #2c3e50;
            padding: 15px 0;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
        }
        
        .navbar .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            color: #2c3e50;
            font-size: 24px;
            font-weight: bold;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .nav-links {
            display: flex;
            gap: 20px;
            align-items: center;
        }
        
        .nav-links a {
            color: #2c3e50;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 20px;
            transition: all 0.3s;
            font-weight: 500;
        }
        
        .nav-links a:hover {
            background: #4facfe;
            color: white;
            transform: translateY(-2px);
        }
        
        .alert {
            padding: 15px;
            margin: 20px 0;
            border-radius: 8px;
            font-weight: 500;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from { transform: translateY(-20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
        .card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin: 20px 0;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }
        
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            text-decoration: none;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s;
            text-align: center;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(79, 172, 254, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #218838 100%);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #495057;
        }
        
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 14px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 16px;
            transition: border 0.3s;
        }
        
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #4facfe;
            box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-card h3 {
            font-size: 32px;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        
        .stat-card p {
            color: #666;
            font-size: 14px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }
        
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }
        
        .badge {
            padding: 5px 12px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 500;
        }
        
        .badge-success {
            background: #d4edda;
            color: #155724;
        }
        
        .badge-warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .badge-danger {
            background: #f8d7da;
            color: #721c24;
        }
        
        .resort-card {
            display: flex;
            gap: 20px;
            padding: 20px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            margin: 15px 0;
            transition: all 0.3s;
        }
        
        .resort-card:hover {
            border-color: #4facfe;
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.1);
        }
        
        .resort-info {
            flex: 1;
        }
        
        .resort-stats {
            display: flex;
            gap: 15px;
            margin-top: 10px;
        }
        
        .resort-stat {
            background: #f8f9fa;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
        }
        
        @media (max-width: 768px) {
            .navbar .container {
                flex-direction: column;
                gap: 15px;
            }
            
            .nav-links {
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .resort-card {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <!-- НАВИГАЦИЯ -->
    <nav class="navbar">
        <div class="container">
            <a href="/" class="logo">🏔️ SkiPass Pro</a>
            <div class="nav-links">
                {% if session.user %}
                    <a href="/dashboard">📊 Панель</a>
                    <a href="/resorts">🏔️ Курорты</a>
                    <a href="/passes">🎫 Ски-пассы</a>
                    <a href="/sales">💰 Продажи</a>
                    {% if session.role == 'admin' or session.role == 'cashier' %}
                        <a href="/new_sale">🛒 Новая продажа</a>
                    {% endif %}
                    {% if session.role == 'admin' %}
                        <a href="/admin">👑 Админ</a>
                    {% endif %}
                    <a href="/profile">👤 {{ session.user }}</a>
                    <a href="/logout" style="background: #dc3545; color: white;">🚪 Выйти</a>
                {% else %}
                    <a href="/login">🔐 Вход</a>
                    <a href="/register">📝 Регистрация</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <!-- ОСНОВНОЙ КОНТЕНТ -->
    <div class="container">
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
        
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

# Шаблоны для разных страниц
INDEX_TEMPLATE = '''
{% extends "base" %}
{% block content %}
<div style="text-align: center; padding: 100px 0; color: #2c3e50;">
    <h1 style="font-size: 48px; margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(255,255,255,0.5);">
        🏔️ SkiPass Pro
    </h1>
    <p style="font-size: 20px; max-width: 600px; margin: 0 auto 40px auto; color: #34495e;">
        Профессиональная система продажи ски-пассов и управления горнолыжными курортами
    </p>
    
    {% if not session.user %}
    <div style="display: flex; gap: 20px; justify-content: center; margin-top: 30px;">
        <a href="/login" class="btn" style="padding: 15px 40px; font-size: 18px;">
            🔐 Войти в систему
        </a>
        <a href="/register" class="btn btn-success" style="padding: 15px 40px; font-size: 18px;">
            📝 Зарегистрироваться
        </a>
    </div>
    {% else %}
    <div style="margin-top: 30px;">
        <a href="/dashboard" class="btn" style="padding: 15px 40px; font-size: 18px;">
            📊 Перейти в панель
        </a>
    </div>
    {% endif %}
</div>

<!-- Блок с информацией о системе -->
<div class="card" style="margin-top: 50px;">
    <h2 style="text-align: center; margin-bottom: 30px;">🎯 Возможности системы</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
        <div style="text-align: center; padding: 20px;">
            <div style="font-size: 40px; margin-bottom: 10px;">🏔️</div>
            <h3>Управление курортами</h3>
            <p>Полная информация о всех горнолыжных курортах</p>
        </div>
        <div style="text-align: center; padding: 20px;">
            <div style="font-size: 40px; margin-bottom: 10px;">🎫</div>
            <h3>Продажа ски-пассов</h3>
            <p>Онлайн продажа и управление ски-пассами</p>
        </div>
        <div style="text-align: center; padding: 20px;">
            <div style="font-size: 40px; margin-bottom: 10px;">📊</div>
            <h3>Аналитика продаж</h3>
            <p>Детальная аналитика и отчетность</p>
        </div>
        <div style="text-align: center; padding: 20px;">
            <div style="font-size: 40px; margin-bottom: 10px;">❄️</div>
            <h3>Снежные условия</h3>
            <p>Мониторинг погоды и состояния склонов</p>
        </div>
    </div>
</div>
{% endblock %}
'''

DASHBOARD_TEMPLATE = '''
{% extends "base" %}
{% block content %}
<div class="card">
    <h1>📊 Панель управления</h1>
    <p style="color: #666; margin-top: 10px; font-size: 18px;">
        Добро пожаловать, <strong>{{ session.user }}</strong>! 🎿
    </p>
</div>

<!-- СТАТИСТИКА -->
<div class="stats-grid">
    <div class="stat-card">
        <div style="font-size: 14px; color: #666; margin-bottom: 10px;">🏔️ Всего курортов</div>
        <h3>{{ stats.total_resorts }}</h3>
    </div>
    <div class="stat-card">
        <div style="font-size: 14px; color: #666; margin-bottom: 10px;">🎫 Продано пассов</div>
        <h3 style="color: #28a745;">{{ stats.total_sales }}</h3>
    </div>
    <div class="stat-card">
        <div style="font-size: 14px; color: #666; margin-bottom: 10px;">💰 Выручка</div>
        <h3 style="color: #17a2b8;">{{ stats.total_revenue }} ₽</h3>
    </div>
    <div class="stat-card">
        <div style="font-size: 14px; color: #666; margin-bottom: 10px;">👥 Пользователей</div>
        <h3>{{ stats.total_users }}</h3>
    </div>
</div>

<!-- ПОСЛЕДНИЕ ПРОДАЖИ -->
<div class="card">
    <h2>💰 Последние продажи</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Клиент</th>
                <th>Курорт</th>
                <th>Пасс</th>
                <th>Сумма</th>
                <th>Статус</th>
            </tr>
        </thead>
        <tbody>
            {% for sale in recent_sales %}
            <tr>
                <td><strong>#{{ sale.id }}</strong></td>
                <td>{{ sale.customer_name }}</td>
                <td>{{ sale.resort_name }}</td>
                <td>{{ sale.pass_name }}</td>
                <td><strong>{{ sale.total_amount }} ₽</strong></td>
                <td>
                    {% if sale.status == 'paid' %}
                        <span class="badge badge-success">✅ Оплачено</span>
                    {% elif sale.status == 'pending' %}
                        <span class="badge badge-warning">⏳ Ожидание</span>
                    {% else %}
                        <span class="badge badge-danger">❌ Отмена</span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- СОСТОЯНИЕ КУРОРТОВ -->
<div class="card">
    <h2>🏔️ Состояние курортов</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px;">
        {% for condition in snow_conditions %}
        <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #4facfe;">
            <h3 style="margin-bottom: 10px;">{{ condition.resort_name }}</h3>
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <div>
                    <div style="font-size: 12px; color: #666;">❄️ Снег</div>
                    <div style="font-size: 18px; font-weight: bold;">{{ condition.snow_depth_cm }} см</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #666;">🌡️ Температура</div>
                    <div style="font-size: 18px; font-weight: bold;">{{ condition.temperature_min }}° / {{ condition.temperature_max }}°</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #666;">☀️ Погода</div>
                    <div style="font-size: 18px; font-weight: bold;">
                        {% if condition.weather_condition == 'sunny' %} ☀️
                        {% elif condition.weather_condition == 'cloudy' %} ☁️
                        {% elif condition.weather_condition == 'snow' %} ❄️
                        {% elif condition.weather_condition == 'blizzard' %} 🌨️
                        {% else %} 🌫️ {% endif %}
                    </div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
'''

# Маршруты Flask
@app.route('/')
def index():
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', INDEX_TEMPLATE),
        title='SkiPass Pro - Главная',
        messages=messages
    )

@app.route('/dashboard')
def dashboard():
    if not session.get('user'):
        return redirect('/login')
    
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    conn = get_db_connection()
    
    if not conn:
        flash('❌ Ошибка подключения к базе данных', 'error')
        return redirect('/')
    
    try:
        with conn.cursor() as cursor:
            # Получаем статистику
            cursor.execute("SELECT COUNT(*) as count FROM resorts")
            total_resorts = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM pass_sales WHERE status = 'paid'")
            total_sales = cursor.fetchone()['count']
            
            cursor.execute("SELECT SUM(total_amount) as total FROM pass_sales WHERE status = 'paid'")
            total_revenue = cursor.fetchone()['total'] or 0
            
            cursor.execute("SELECT COUNT(*) as count FROM users")
            total_users = cursor.fetchone()['count']
            
            # Последние продажи
            cursor.execute("""
                SELECT ps.*, r.name as resort_name, pt.name as pass_name
                FROM pass_sales ps
                JOIN resorts r ON ps.resort_id = r.id
                JOIN pass_types pt ON ps.pass_type_id = pt.id
                ORDER BY ps.created_at DESC LIMIT 10
            """)
            recent_sales = cursor.fetchall()
            
            # Снежные условия
            cursor.execute("""
                SELECT sc.*, r.name as resort_name
                FROM snow_conditions sc
                JOIN resorts r ON sc.resort_id = r.id
                WHERE sc.date = CURDATE()
                ORDER BY r.name
            """)
            snow_conditions = cursor.fetchall()
            
            stats = {
                'total_resorts': total_resorts,
                'total_sales': total_sales,
                'total_revenue': round(total_revenue, 2),
                'total_users': total_users
            }
            
            return render_template_string(
                BASE_TEMPLATE.replace('{% block content %}{% endblock %}', DASHBOARD_TEMPLATE),
                title='Панель управления',
                messages=messages,
                stats=stats,
                recent_sales=recent_sales,
                snow_conditions=snow_conditions
            )
            
    except Exception as e:
        flash(f'❌ Ошибка загрузки данных: {str(e)}', 'error')
        return redirect('/')
    finally:
        conn.close()

@app.route('/resorts')
def resorts():
    if not session.get('user'):
        return redirect('/login')
    
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    conn = get_db_connection()
    
    if not conn:
        flash('❌ Ошибка подключения к базе данных', 'error')
        return redirect('/')
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, 
                       (SELECT COUNT(*) FROM lifts WHERE resort_id = r.id AND status = 'operational') as operational_lifts,
                       (SELECT weather_condition FROM snow_conditions WHERE resort_id = r.id AND date = CURDATE() LIMIT 1) as weather
                FROM resorts r
                WHERE r.is_active = 1
                ORDER BY r.name
            """)
            resorts_data = cursor.fetchall()
            
            # Получаем снежные условия
            cursor.execute("""
                SELECT sc.*, r.name as resort_name
                FROM snow_conditions sc
                JOIN resorts r ON sc.resort_id = r.id
                WHERE sc.date = CURDATE()
            """)
            snow_data = cursor.fetchall()
            
            return render_template_string(
                BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
                {% extends "base" %}
                {% block content %}
                <div class="card">
                    <h1>🏔️ Горнолыжные курорты</h1>
                    <p style="color: #666; margin-top: 10px;">
                        Список всех доступных горнолыжных курортов
                    </p>
                </div>
                
                <div class="card">
                    <h2>❄️ Текущие снежные условия</h2>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-top: 20px;">
                        {% for snow in snow_data %}
                        <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; border-radius: 10px;">
                            <h3 style="margin-bottom: 15px;">{{ snow.resort_name }}</h3>
                            <div style="display: flex; justify-content: space-between;">
                                <div>
                                    <div style="font-size: 12px; opacity: 0.9;">Снежный покров</div>
                                    <div style="font-size: 24px; font-weight: bold;">{{ snow.snow_depth_cm }} см</div>
                                </div>
                                <div>
                                    <div style="font-size: 12px; opacity: 0.9;">Новый снег</div>
                                    <div style="font-size: 24px; font-weight: bold;">{{ snow.new_snow_cm }} см</div>
                                </div>
                                <div>
                                    <div style="font-size: 12px; opacity: 0.9;">Температура</div>
                                    <div style="font-size: 24px; font-weight: bold;">{{ snow.temperature_max }}°C</div>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                
                {% for resort in resorts_data %}
                <div class="resort-card">
                    <div style="width: 100px; height: 100px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                         border-radius: 10px; display: flex; align-items: center; justify-content: center; color: white; font-size: 40px;">
                        🏔️
                    </div>
                    <div class="resort-info">
                        <h3>{{ resort.name }}</h3>
                        <p style="color: #666; margin: 10px 0;">{{ resort.description }}</p>
                        <div class="resort-stats">
                            <div class="resort-stat">📍 {{ resort.location }}</div>
                            <div class="resort-stat">⛷️ {{ resort.slopes_count }} трасс</div>
                            <div class="resort-stat">🚡 {{ resort.operational_lifts }}/{{ resort.lifts_count }} подъемников</div>
                            <div class="resort-stat">
                                {% if resort.weather == 'sunny' %} ☀️ Солнечно
                                {% elif resort.weather == 'cloudy' %} ☁️ Облачно
                                {% elif resort.weather == 'snow' %} ❄️ Снег
                                {% elif resort.weather == 'blizzard' %} 🌨️ Метель
                                {% else %} 🌫️ Туман {% endif %}
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 10px; min-width: 150px;">
                        <a href="/passes?resort={{ resort.id }}" class="btn">🎫 Смотреть пассы</a>
                        <a href="/new_sale?resort={{ resort.id }}" class="btn btn-success">🛒 Купить пасс</a>
                    </div>
                </div>
                {% endfor %}
                {% endblock %}
                '''),
                title='Курорты',
                messages=messages,
                resorts_data=resorts_data,
                snow_data=snow_data
            )
            
    except Exception as e:
        flash(f'❌ Ошибка загрузки данных: {str(e)}', 'error')
        return redirect('/')
    finally:
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user'):
        return redirect('/dashboard')
    
    if request.method == 'POST':
        username = request.form.get('login')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('❌ Ошибка подключения к базе данных', 'error')
            return redirect('/login')
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE login = %s", (username,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password_hash'], password):
                    if user['is_active']:
                        session['user'] = user['login']
                        session['user_id'] = user['id']
                        session['role'] = 'admin' if user['role_id'] == 2 else 'cashier' if user['role_id'] == 3 else 'user'
                        flash('✅ Вход выполнен успешно!', 'success')
                        return redirect('/dashboard')
                    else:
                        flash('❌ Аккаунт заблокирован', 'error')
                else:
                    flash('❌ Неверный логин или пароль', 'error')
        except Exception as e:
            flash(f'❌ Ошибка при входе: {str(e)}', 'error')
        finally:
            conn.close()
    
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
        {% extends "base" %}
        {% block content %}
        <div style="max-width: 400px; margin: 100px auto;">
            <div class="card">
                <h2 style="text-align: center; margin-bottom: 30px;">🔐 Вход в систему</h2>
                <form method="POST" action="/login">
                    <div class="form-group">
                        <label>👤 Логин</label>
                        <input type="text" name="login" placeholder="Введите логин" required>
                    </div>
                    <div class="form-group">
                        <label>🔒 Пароль</label>
                        <input type="password" name="password" placeholder="Введите пароль" required>
                    </div>
                    <button type="submit" class="btn" style="width: 100%; margin-top: 10px;">
                        📥 Войти в систему
                    </button>
                </form>
                <p style="text-align: center; margin-top: 25px; color: #666;">
                    Нет аккаунта? <a href="/register" style="color: #4facfe;">Зарегистрируйтесь</a><br>
                    <small style="color: #888;">Тестовый аккаунт: <b>admin</b> / <b>admin123</b></small>
                </p>
            </div>
        </div>
        {% endblock %}
        '''),
        title='Вход в систему',
        messages=messages
    )

@app.route('/logout')
def logout():
    session.clear()
    flash('✅ Вы успешно вышли из системы', 'info')
    return redirect('/')

if __name__ == '__main__':
    if init_database():
        print("🎿 Запуск системы SkiPass Pro...")
        print("🌐 Откройте в браузере: http://localhost:5000")
        print("👤 Тестовый аккаунт: admin / admin123")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("❌ Не удалось инициализировать базу данных")