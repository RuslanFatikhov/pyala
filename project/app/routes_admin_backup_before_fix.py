import os
import logging
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from app.services.products import ProductService
from app.services.orders import OrderService
from app.services.validators import ProductCSVValidator

# Инициализация сервисов
product_service = ProductService()
order_service = OrderService()
csv_validator = ProductCSVValidator()

# Blueprint
admin_bp = Blueprint('admin', __name__)

# Настройка безопасности
SECURITY_ENABLED = os.getenv('SECURITY_ENABLED', 'true').lower() == 'true'
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SECURITY_ENABLED:
            return f(*args, **kwargs)
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

def secure_admin_required(f):
    """Декоратор для проверки авторизации (только при включенной безопасности)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SECURITY_ENABLED:
            flash('Система безопасности отключена. Включите SECURITY_ENABLED=true', 'warning')
            return redirect(url_for('admin.dashboard'))
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if not SECURITY_ENABLED:
        session['admin_logged_in'] = True
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Добро пожаловать в админ-панель!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Неверные данные для входа', 'error')
        return render_template('admin/login.html')
    
    return render_template('admin/login.html')

@admin_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@login_required
def dashboard():
    try:
        stats = {
            'total_products': product_service.get_products_count(),
            'active_products': product_service.get_active_products_count(),
            'total_orders': order_service.get_orders_count(),
            'new_orders': order_service.get_new_orders_count(),
            'security_enabled': SECURITY_ENABLED
        }
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error loading dashboard: {e}")
        flash('Ошибка загрузки дашборда', 'error')
        return render_template('admin/dashboard.html', stats={
            'total_products': 0, 'active_products': 0,
            'total_orders': 0, 'new_orders': 0,
            'security_enabled': SECURITY_ENABLED
        })


@admin_bp.route('/orders')
@login_required
def orders_list():
    try:
        status_filter = request.args.get('status', '')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        orders, total_pages = order_service.get_orders_paginated(
            status_filter=status_filter, page=page, per_page=per_page)
        
        return render_template('admin/orders_list.html',
                             orders=orders, current_page=page,
                             total_pages=total_pages, status_filter=status_filter,
                             security_enabled=SECURITY_ENABLED)
    except Exception as e:
        logging.error(f"Error loading orders: {e}")
        return render_template('admin/orders_list.html', orders=[], 
                             current_page=1, total_pages=0, status_filter='',
                             security_enabled=SECURITY_ENABLED)

@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    try:
        new_status = request.form.get('status')
        if new_status not in ['new', 'in_progress', 'shipped', 'done', 'cancelled']:
            flash('Некорректный статус заказа', 'error')
            return redirect(url_for('admin.orders_list'))
        
        success = order_service.update_order_status(order_id, new_status)
        if success:
            flash(f'Статус заказа #{order_id} изменен на: {new_status}', 'success')
        else:
            flash(f'Ошибка изменения статуса заказа #{order_id}', 'error')
        return redirect(url_for('admin.orders_list'))
    except Exception as e:
        logging.error(f"Error updating order status: {e}")
        flash('Ошибка обновления статуса заказа', 'error')
        return redirect(url_for('admin.orders_list'))

@admin_bp.route('/orders/download')
@login_required
def download_orders():
    """Скачивание файла заказов"""
    try:
        csv_path = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        if not os.path.exists(csv_path):
            flash('Файл заказов не найден', 'error')
            return redirect(url_for('admin.orders_list'))
        
        timestamp = datetime.now().strftime("%Y%m%d")
        return send_file(csv_path, as_attachment=True, 
                        download_name=f'orders_export_{timestamp}.csv')
        
    except Exception as e:
        logging.error(f"Error downloading orders CSV: {e}")
        flash('Ошибка скачивания файла', 'error')
        return redirect(url_for('admin.orders_list'))

@admin_bp.route('/products/download')
@login_required
def download_products():
    """Скачивание текущего products.csv"""
    try:
        csv_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
        if not os.path.exists(csv_path):
            flash('Файл товаров не найден', 'error')
            return redirect(url_for('admin.dashboard'))
        return send_file(csv_path, as_attachment=True, download_name='products.csv')
    except Exception as e:
        logging.error(f"Error downloading products CSV: {e}")
        flash('Ошибка скачивания файла', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/products/upload', methods=['GET', 'POST'])
@login_required
def upload_products():
    """Загрузка нового products.csv"""
    if request.method == 'GET':
        return render_template('admin/products_upload.html')
    
    try:
        # Проверка файла
        if 'file' not in request.files:
            flash('Файл не выбран', 'error')
            return render_template('admin/products_upload.html')
        
        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран', 'error')
            return render_template('admin/products_upload.html')
        
        if not file.filename.endswith('.csv'):
            flash('Файл должен иметь расширение .csv', 'error')
            return render_template('admin/products_upload.html')
        
        # Безопасное имя файла
        filename = secure_filename(file.filename)
        
        # Чтение содержимого файла
        content = file.read().decode('utf-8')
        
        # DRY-RUN валидация
        is_valid, errors = csv_validator.validate_csv_content(content)
        
        if not is_valid:
            return render_template('admin/products_upload.html', 
                                 validation_errors=errors)
        
        # Создание бэкапа текущего файла
        csv_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
        if os.path.exists(csv_path):
            backup_dir = './data/backups'
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{backup_dir}/products_backup_{timestamp}.csv"
            
            import shutil
            shutil.copy2(csv_path, backup_path)
            flash(f'Создан бэкап: {backup_path}', 'info')
        
        # Сохранение нового файла
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Перезагрузка данных в сервисе
        product_service.reload_products()
        
        flash('Файл товаров успешно загружен!', 'success')
        return redirect(url_for('admin.products_list'))
        
    except Exception as e:
        logging.error(f"Error uploading products CSV: {e}")
        flash('Ошибка загрузки файла', 'error')
        return render_template('admin/products_upload.html')

@admin_bp.route('/analytics')
@login_required
def analytics():
    """Страница аналитики"""
    try:
        # Собираем статистику
        total_products = product_service.get_products_count()
        active_products = product_service.get_active_products_count()
        total_orders = order_service.get_orders_count()
        new_orders = order_service.get_new_orders_count()
        
        # Статистика по категориям
        all_products = product_service.get_all_products()
        categories_stats = {}
        for product in all_products:
            cat = product['category']
            if cat not in categories_stats:
                categories_stats[cat] = {'count': 0, 'total_value': 0}
            categories_stats[cat]['count'] += 1
            categories_stats[cat]['total_value'] += product['stock'] * product['price']
        
        return render_template('admin/analytics.html', stats={
            'total_products': total_products,
            'active_products': active_products,  
            'total_orders': total_orders,
            'new_orders': new_orders,
            'categories_stats': categories_stats
        })
    except Exception as e:
        logging.error(f"Error loading analytics: {e}")
        flash('Ошибка загрузки аналитики', 'error')
        return redirect(url_for('admin.dashboard'))
    
# Добавляем в app/routes/routes_admin.py эти маршруты для CRUD товаров

@admin_bp.route('/products')
@login_required
def products_list():
    """Список товаров с фильтрами"""
    try:
        # Получаем параметры фильтрации
        search = request.args.get('search', '').strip()
        category_filter = request.args.get('category', '').strip()
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # Получаем товары с фильтрами
        if search or category_filter:
            products = product_service.search_products(
                query=search,
                category=category_filter
            )
        else:
            products = product_service.get_all_products()
        
        # Пагинация
        total = len(products)
        start = (page - 1) * per_page
        end = start + per_page
        products_page = products[start:end]
        
        # Получаем список категорий для фильтра
        categories = product_service.get_categories()
        
        return render_template('admin/products_list.html',
                             products=products_page,
                             categories=categories,
                             search=search,
                             category_filter=category_filter,
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=(total + per_page - 1) // per_page)
    
    except Exception as e:
        print("DEBUG products_list exception:", e)
        logging.error(f"Error in products list: {e}")
        flash('Ошибка загрузки товаров', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/products/create', methods=['GET', 'POST'])
def product_create():
    """Создание нового товара"""
    try:
        if request.method == 'POST':
            # Получаем данные формы
            form_data = request.form.to_dict()
            
            # Валидируем данные
            errors = product_service.validate_product_data(form_data)
            
            if not errors:
                # Создаем товар
                success = product_service.create_product(form_data)
                
                if success:
                    flash(f'Товар "{form_data.get("title")}" успешно создан', 'success')
                    return redirect(url_for('admin.products_list'))
                else:
                    flash('Ошибка при создании товара', 'error')
            
            # Если есть ошибки, показываем форму с ошибками
            return render_template('admin/product_edit.html',
                                 product=None,
                                 form_data=form_data,
                                 errors=errors,
                                 categories=product_service.get_categories(),
                                 is_create=True)
        
        # GET запрос - показываем пустую форму
        # Генерируем предварительный SKU
        suggested_sku = f"PROD-{datetime.now().strftime('%m%d')}-001"
        counter = 1
        while product_service.get_product_by_sku(suggested_sku):
            counter += 1
            suggested_sku = f"PROD-{datetime.now().strftime('%m%d')}-{counter:03d}"
        
        return render_template('admin/product_edit.html',
                             product=None,
                             form_data={'sku': suggested_sku},
                             errors={},
                             categories=product_service.get_categories(),
                             is_create=True)
    
    except Exception as e:
        logging.error(f"Error creating product: {e}")
        flash('Ошибка при создании товара', 'error')
        return redirect(url_for('admin.products_list'))

@admin_bp.route('/products/<sku>/edit', methods=['GET', 'POST'])
def product_edit(sku):
    """Редактирование товара"""
    try:
        product = product_service.get_product_by_sku(sku)
        if not product:
            flash('Товар не найден', 'error')
            return redirect(url_for('admin.products_list'))
        
        if request.method == 'POST':
            # Получаем данные формы
            form_data = request.form.to_dict()
            
            # Валидируем данные (передаем текущий SKU для исключения из проверки дубликатов)
            errors = product_service.validate_product_data(form_data, sku)
            
            if not errors:
                # Обновляем товар
                success = product_service.update_product(sku, form_data)
                
                if success:
                    flash(f'Товар "{form_data.get("title")}" успешно обновлен', 'success')
                    return redirect(url_for('admin.products_list'))
                else:
                    flash('Ошибка при обновлении товара', 'error')
            
            # Если есть ошибки, показываем форму с ошибками
            return render_template('admin/product_edit.html',
                                 product=product,
                                 form_data=form_data,
                                 errors=errors,
                                 categories=product_service.get_categories(),
                                 is_create=False)
        
        # GET запрос - показываем форму с данными товара
        # Подготавливаем данные для формы
        form_data = product.copy()
        
        # Преобразуем списки в строки для формы
        if isinstance(form_data.get('tags'), list):
            form_data['tags'] = ', '.join(form_data['tags'])
        
        if isinstance(form_data.get('images'), list):
            form_data['images'] = ', '.join(form_data['images'])
        
        return render_template('admin/product_edit.html',
                             product=product,
                             form_data=form_data,
                             errors={},
                             categories=product_service.get_categories(),
                             is_create=False)
    
    except Exception as e:
        logging.error(f"Error editing product {sku}: {e}")
        flash('Ошибка при редактировании товара', 'error')
        return redirect(url_for('admin.products_list'))

@admin_bp.route('/products/<sku>/delete', methods=['POST'])
def product_delete(sku):
    """Удаление товара"""
    try:
        product = product_service.get_product_by_sku(sku)
        if not product:
            return jsonify({'error': 'Товар не найден'}), 404
        
        # Удаляем товар
        success = product_service.delete_product(sku)
        
        if success:
            # Для AJAX запросов
            if request.is_json:
                return jsonify({'ok': True, 'message': 'Товар успешно удален'})
            
            # Для обычных форм
            flash(f'Товар "{product.get("title")}" удален', 'success')
            return redirect(url_for('admin.products_list'))
        else:
            if request.is_json:
                return jsonify({'error': 'Ошибка при удалении товара'}), 500
            
            flash('Ошибка при удалении товара', 'error')
            return redirect(url_for('admin.products_list'))
    
    except Exception as e:
        logging.error(f"Error deleting product {sku}: {e}")
        
        if request.is_json:
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        flash('Ошибка при удалении товара', 'error')
        return redirect(url_for('admin.products_list'))

@admin_bp.route('/products/<sku>/duplicate', methods=['POST'])
def product_duplicate(sku):
    """Дублирование товара"""
    try:
        original_product = product_service.get_product_by_sku(sku)
        if not original_product:
            flash('Товар не найден', 'error')
            return redirect(url_for('admin.products_list'))
        
        # Создаем копию товара
        new_product = original_product.copy()
        
        # Генерируем новый SKU
        base_title = new_product.get('title', 'Product')
        new_sku = product_service.generate_sku(base_title)
        new_product['sku'] = new_sku
        new_product['title'] = f"{new_product['title']} (копия)"
        
        # Создаем дубликат
        success = product_service.create_product(new_product)
        
        if success:
            flash(f'Товар продублирован с SKU: {new_sku}', 'success')
            return redirect(url_for('admin.product_edit', sku=new_sku))
        else:
            flash('Ошибка при дублировании товара', 'error')
            return redirect(url_for('admin.products_list'))
    
    except Exception as e:
        logging.error(f"Error duplicating product {sku}: {e}")
        flash('Ошибка при дублировании товара', 'error')
        return redirect(url_for('admin.products_list'))

@admin_bp.route('/api/products/search')
def api_products_search():
    """API для поиска товаров (для автокомплита)"""
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        
        if not query or len(query) < 2:
            return jsonify([])
        
        products = product_service.search_products(query=query)
        
        # Ограничиваем результаты
        results = []
        for product in products[:limit]:
            results.append({
                'sku': product['sku'],
                'title': product['title'],
                'price': product['price'],
                'stock': product['stock']
            })
        
        return jsonify(results)
    
    except Exception as e:
        logging.error(f"Error in API products search: {e}")
        return jsonify({'error': 'Internal server error'}), 500