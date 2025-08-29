from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from .services.products import ProductService
from .services.validators import ProductCSVValidator
import os
import logging
from datetime import datetime

# Импорты для безопасности
try:
    from .services.secure_orders import SecureOrderService
    SECURITY_ENABLED = True
    print("Система безопасности включена")
except ImportError:
    from .services.orders import OrderService
    SECURITY_ENABLED = False
    print("Работаем без модулей безопасности")

admin_bp = Blueprint('admin', __name__)
product_service = ProductService()

if SECURITY_ENABLED:
    order_service = SecureOrderService()
else:
    order_service = OrderService()

csv_validator = ProductCSVValidator()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('admin/login.html')
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
    
    if username == admin_username and password == admin_password:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        session['session_start'] = datetime.now().isoformat()
        flash('Вы успешно авторизованы', 'success')
        return redirect(url_for('admin.dashboard'))
    else:
        flash('Неверные данные для входа', 'error')
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

# Остальные методы остаются из исходного файла...
@admin_bp.route('/products/download')
@login_required
def download_products():
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
    if request.method == 'GET':
        return render_template('admin/products_upload.html')
    try:
        if 'file' not in request.files:
            flash('Файл не выбран', 'error')
            return render_template('admin/products_upload.html')
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.csv'):
            flash('Выберите CSV файл', 'error')
            return render_template('admin/products_upload.html')
        
        content = file.read().decode('utf-8')
        is_valid, errors = csv_validator.validate_csv_content(content)
        if not is_valid:
            return render_template('admin/products_upload.html', validation_errors=errors)
        
        csv_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
        backup_dir = os.getenv('BACKUP_DIR', './data/backups')
        
        if os.path.exists(csv_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            backup_path = os.path.join(backup_dir, f'products_{timestamp}.csv')
            os.makedirs(backup_dir, exist_ok=True)
            with open(csv_path, 'r', encoding='utf-8') as src:
                with open(backup_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
        
        temp_path = csv_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(temp_path, csv_path)
        product_service.invalidate_cache()
        
        flash('Файл успешно загружен и кэш обновлен', 'success')
        return redirect(url_for('admin.dashboard'))
    except Exception as e:
        logging.error(f"Error uploading products CSV: {e}")
        flash(f'Ошибка загрузки файла: {str(e)}', 'error')
        return render_template('admin/products_upload.html')
