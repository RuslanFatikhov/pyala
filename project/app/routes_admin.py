from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .services.products import ProductService
from .services.orders import OrderService
from .services.validators import ProductCSVValidator

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Инициализация сервисов
product_service = ProductService()
order_service = OrderService()
csv_validator = ProductCSVValidator()

@admin_bp.route('/')
def dashboard():
    """Главная страница админки"""
    return render_template('admin/dashboard.html')

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в админку"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Простая проверка (замените на реальную аутентификацию)
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            flash('Успешный вход в систему', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Неверные данные для входа', 'error')
    
    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    """Выход из админки"""
    session.pop('admin_logged_in', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/products')
def products():
    """Управление товарами"""
    all_products = product_service.get_all_products()
    return render_template('admin/products.html', products=all_products)

@admin_bp.route('/orders')
def orders():
    """Управление заказами"""
    all_orders = order_service.get_all_orders()
    return render_template('admin/orders.html', orders=all_orders)

@admin_bp.route('/upload-csv', methods=['GET', 'POST'])
def upload_csv():
    """Загрузка CSV с товарами"""
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Файл не выбран', 'error')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('Файл не выбран', 'error')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            content = file.read().decode('utf-8')
            is_valid, errors = csv_validator.validate_csv_content(content)
            
            if is_valid:
                flash('CSV файл успешно загружен', 'success')
                # Здесь будет логика сохранения товаров
            else:
                for error in errors:
                    flash(error, 'error')
        else:
            flash('Разрешены только CSV файлы', 'error')
    
    return render_template('admin/upload_csv.html')

# Декоратор для проверки авторизации (добавьте перед защищенными роутами)
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function