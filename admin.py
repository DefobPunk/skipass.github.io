# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///skipass.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')  # 'admin' или 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class SkiPass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    pass_type = db.Column(db.String(50), nullable=False)  # 'daily', 'evening', 'seasonal', 'child', 'family'
    price = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # 'active', 'inactive'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    skipass_id = db.Column(db.Integer, db.ForeignKey('ski_pass.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'paid', 'cancelled'
    payment_method = db.Column(db.String(50))
    
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    skipass = db.relationship('SkiPass', backref=db.backref('orders', lazy=True))

class Statistic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    total_orders = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0.0)
    active_passes = db.Column(db.Integer, default=0)
    new_users = db.Column(db.Integer, default=0)

# Создание базы данных
with app.app_context():
    db.create_all()
    
    # Создание администратора по умолчанию, если его нет
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@skipass.ru',
            full_name='Алексей Иванов',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Добавление тестовых данных
        test_passes = [
            SkiPass(
                name='Стандарт 1 день',
                pass_type='daily',
                price=2500.0,
                duration_days=1,
                start_date=datetime(2024, 12, 1),
                end_date=datetime(2025, 3, 31),
                description='Однодневный ски-пасс на все подъемники',
                status='active'
            ),
            SkiPass(
                name='Вечерний',
                pass_type='evening',
                price=1800.0,
                duration_days=1,
                start_date=datetime(2024, 12, 1),
                end_date=datetime(2025, 3, 31),
                description='Вечерний ски-пасс (с 16:00 до закрытия)',
                status='active'
            ),
            SkiPass(
                name='Сезонный',
                pass_type='seasonal',
                price=45000.0,
                duration_days=120,
                start_date=datetime(2024, 12, 1),
                end_date=datetime(2025, 4, 15),
                description='Сезонный безлимитный абонемент',
                status='active'
            ),
            SkiPass(
                name='Детский 1 день',
                pass_type='child',
                price=1500.0,
                duration_days=1,
                start_date=datetime(2024, 12, 1),
                end_date=datetime(2025, 3, 31),
                description='Детский однодневный ски-пасс (до 12 лет)',
                status='inactive'
            )
        ]
        
        for pass_item in test_passes:
            db.session.add(pass_item)
        
        db.session.commit()

# Вспомогательные функции
def generate_order_number():
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    import random
    random_part = random.randint(100, 999)
    return f"ORD-{timestamp}-{random_part}"

def check_admin_login():
    """Проверка, авторизован ли администратор"""
    return 'user_id' in session and User.query.get(session['user_id']).role == 'admin'

# API эндпоинты
@app.route('/')
def index():
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.role == 'admin':
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({'success': True, 'redirect': '/admin/dashboard'})
        
        return jsonify({'success': False, 'error': 'Неверные учетные данные'})
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not check_admin_login():
        return redirect(url_for('admin_login'))
    
    # Получение статистики
    total_orders = Order.query.count()
    active_passes = SkiPass.query.filter_by(status='active').count()
    total_users = User.query.count()
    
    # Расчет выручки
    total_revenue = db.session.query(db.func.sum(Order.total_price)).filter_by(status='paid').scalar() or 0
    
    # Последние заказы
    recent_orders = Order.query.order_by(Order.order_date.desc()).limit(10).all()
    
    # Форматирование заказов для отображения
    orders_data = []
    for order in recent_orders:
        orders_data.append({
            'id': order.id,
            'order_number': order.order_number,
            'user_name': order.user.full_name or order.user.username,
            'skipass_name': order.skipass.name,
            'total_price': order.total_price,
            'order_date': order.order_date.strftime('%d.%m.%Y'),
            'status': order.status
        })
    
    return render_template('admin_dashboard.html', 
                         total_orders=total_orders,
                         active_passes=active_passes,
                         total_users=total_users,
                         total_revenue=total_revenue,
                         recent_orders=orders_data)

# API для ски-пассов
@app.route('/api/skipasses', methods=['GET'])
def get_skipasses():
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    skipasses = SkiPass.query.all()
    result = []
    
    for pass_item in skipasses:
        result.append({
            'id': pass_item.id,
            'name': pass_item.name,
            'type': pass_item.pass_type,
            'price': pass_item.price,
            'duration_days': pass_item.duration_days,
            'start_date': pass_item.start_date.strftime('%Y-%m-%d'),
            'end_date': pass_item.end_date.strftime('%Y-%m-%d'),
            'description': pass_item.description,
            'status': pass_item.status,
            'formatted_date': f"{pass_item.start_date.strftime('%d.%m.%Y')} - {pass_item.end_date.strftime('%d.%m.%Y')}"
        })
    
    return jsonify(result)

@app.route('/api/skipasses', methods=['POST'])
def create_skipass():
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    data = request.get_json()
    
    try:
        new_pass = SkiPass(
            name=data['name'],
            pass_type=data['type'],
            price=float(data['price']),
            duration_days=int(data['duration_days']),
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d'),
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d'),
            description=data.get('description', ''),
            status=data.get('status', 'active')
        )
        
        db.session.add(new_pass)
        db.session.commit()
        
        return jsonify({'success': True, 'id': new_pass.id})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/skipasses/<int:pass_id>', methods=['PUT'])
def update_skipass(pass_id):
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    pass_item = SkiPass.query.get_or_404(pass_id)
    data = request.get_json()
    
    try:
        pass_item.name = data.get('name', pass_item.name)
        pass_item.pass_type = data.get('type', pass_item.pass_type)
        pass_item.price = float(data.get('price', pass_item.price))
        pass_item.duration_days = int(data.get('duration_days', pass_item.duration_days))
        pass_item.status = data.get('status', pass_item.status)
        
        if 'description' in data:
            pass_item.description = data['description']
        
        if 'start_date' in data:
            pass_item.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        
        if 'end_date' in data:
            pass_item.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/skipasses/<int:pass_id>', methods=['DELETE'])
def delete_skipass(pass_id):
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    pass_item = SkiPass.query.get_or_404(pass_id)
    
    # Проверка, есть ли активные заказы для этого пасса
    active_orders = Order.query.filter_by(skipass_id=pass_id, status='paid').count()
    if active_orders > 0:
        return jsonify({'error': 'Нельзя удалить тариф с активными заказами'}), 400
    
    db.session.delete(pass_item)
    db.session.commit()
    
    return jsonify({'success': True})

# API для пользователей
@app.route('/api/users', methods=['GET'])
def get_users():
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    users = User.query.all()
    result = []
    
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'created_at': user.created_at.strftime('%d.%m.%Y %H:%M'),
            'order_count': len(user.orders)
        })
    
    return jsonify(result)

# API для заказов
@app.route('/api/orders', methods=['GET'])
def get_orders():
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    orders = Order.query.order_by(Order.order_date.desc()).all()
    result = []
    
    for order in orders:
        result.append({
            'id': order.id,
            'order_number': order.order_number,
            'user_name': order.user.full_name or order.user.username,
            'skipass_name': order.skipass.name,
            'quantity': order.quantity,
            'total_price': order.total_price,
            'order_date': order.order_date.strftime('%d.%m.%Y %H:%M'),
            'status': order.status,
            'payment_method': order.payment_method
        })
    
    return jsonify(result)

@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    order = Order.query.get_or_404(order_id)
    data = request.get_json()
    
    new_status = data.get('status')
    if new_status not in ['pending', 'paid', 'cancelled']:
        return jsonify({'error': 'Неверный статус'}), 400
    
    order.status = new_status
    db.session.commit()
    
    return jsonify({'success': True})

# API для статистики
@app.route('/api/stats', methods=['GET'])
def get_stats():
    if not check_admin_login():
        return jsonify({'error': 'Не авторизован'}), 401
    
    # Статистика за последние 30 дней
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Заказы за период
    period_orders = Order.query.filter(
        Order.order_date >= start_date
    ).all()
    
    # Выручка за период
    period_revenue = sum([o.total_price for o in period_orders if o.status == 'paid'])
    
    # Новые пользователи за период
    new_users = User.query.filter(
        User.created_at >= start_date
    ).count()
    
    # Активные пассы
    active_passes = SkiPass.query.filter_by(status='active').count()
    
    return jsonify({
        'total_orders': len(period_orders),
        'total_revenue': period_revenue,
        'new_users': new_users,
        'active_passes': active_passes,
        'period': {
            'start': start_date.strftime('%d.%m.%Y'),
            'end': end_date.strftime('%d.%m.%Y')
        }
    })

# HTML шаблоны
@app.route('/templates/<template_name>')
def serve_template(template_name):
    """Отдача HTML шаблонов"""
    if template_name == 'admin_login.html':
        return '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Вход в админ-панель | Ски-Пассы</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
                body { background: linear-gradient(135deg, #e3f2fd 0%, #f5f7fa 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
                .login-container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
                h1 { color: #1e88e5; margin-bottom: 30px; text-align: center; }
                .form-group { margin-bottom: 20px; }
                label { display: block; margin-bottom: 5px; color: #333; font-weight: 600; }
                input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
                button { width: 100%; padding: 12px; background: #1e88e5; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: 600; cursor: pointer; }
                button:hover { background: #1565c0; }
                .error { color: #f44336; margin-top: 10px; text-align: center; }
                .logo { text-align: center; margin-bottom: 20px; color: #1e88e5; font-size: 24px; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="login-container">
                <div class="logo">
                    <i class="fas fa-skiing"></i> Админ-панель Ски-Пассы
                </div>
                <h1>Вход в систему</h1>
                <form id="loginForm">
                    <div class="form-group">
                        <label>Имя пользователя</label>
                        <input type="text" name="username" value="admin" required>
                    </div>
                    <div class="form-group">
                        <label>Пароль</label>
                        <input type="password" name="password" value="admin123" required>
                    </div>
                    <button type="submit">Войти</button>
                    <div class="error" id="errorMessage"></div>
                </form>
            </div>
            <script>
                document.getElementById('loginForm').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    const formData = new FormData(this);
                    const response = await fetch('/admin/login', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();
                    if (result.success) {
                        window.location.href = result.redirect;
                    } else {
                        document.getElementById('errorMessage').textContent = result.error;
                    }
                });
            </script>
        </body>
        </html>
        '''
    
    return 'Template not found', 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)