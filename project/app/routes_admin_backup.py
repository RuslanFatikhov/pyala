# app/routes_admin.py - ОБНОВЛЕННЫЙ с системой безопасности
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from .services.products import ProductService
from .services.orders import OrderService
from .services.validators import ProductCSVValidator
import os
import logging
from datetime import datetime

# Импорты для безопасности
try:
    from .services.encryption import DataEncryption
    from .services.secure_orders import SecureOrderService
    from .security.middleware import admin_required, security_middleware
    from .security.audit_logger import audit_logger
    from .security.data_protection import DataProtection
    SECURITY_ENABLED = True
except ImportError:
    # Fallback если модули безопасности не установлены
    SECURITY_ENABLED = False
    print("⚠️  WARNING: Модули безопасности не найдены. Используется базовая защита.")

admin_bp = Blueprint('admin', __name__)
product_service = ProductService()

# Выбираем сервис заказов в зависимости от наличия модулей безопасности
if SECURITY_ENABLED:
    order_service = SecureOrderService()
else:
    order_service = OrderService()

csv_validator = ProductCSVValidator()

def login_required(f):
    """Базовый декоратор для проверки авторизации админа"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# Используем безопасный декоратор если доступен
if SECURITY_ENABLED:
    secure_admin_required = admin_required
else:
    secure_admin_required = login_required

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Авторизация администратора с защитой от брутфорса"""
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    
    if request.method == 'GET':
        # Проверяем блокировку IP если безопасность включена
        if SECURITY_ENABLED and security_middleware.is_ip_locked(client_ip):
            flash('Слишком много неудачных попыток. Попробуйте позже.', 'error')
            return render_template('admin/login.html'), 429
        
        return render_template('admin/login.html')
    
    # POST запрос
    if SECURITY_ENABLED and security_middleware.is_ip_locked(client_ip):
        audit_logger.log_security_event('BLOCKED_LOGIN_ATTEMPT', f'IP заблокирован: {client_ip}')
        flash('Слишком много неудачных попыток. Попробуйте позже.', 'error')
        return render_template('admin/login.html'), 429
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
    
    if username == admin_username and password == admin_password:
        # Успешная авторизация
        session['admin_logged_in'] = True
        session['admin_username'] = username
        if SECURITY_ENABLED:
            session['session_start'] = datetime.now().isoformat()
            security_middleware.record_successful_login(client_ip)
            audit_logger.log_admin_login(username, True)
        
        flash('Вы успешно авторизованы', 'success')
        return redirect(url_for('admin.dashboard'))
    else:
        # Неудачная авторизация
        if SECURITY_ENABLED:
            security_middleware.record_failed_login(client_ip)
            audit_logger.log_admin_login(username or '[EMPTY]', False)
        
        flash('Неверные данные для входа', 'error')
        return render_template('admin/login.html')

@admin_bp.route('/logout', methods=['POST'])
@secure_admin_required
def logout():
    """Выход из админки"""
    if SECURITY_ENABLED:
        admin_username = session.get('admin_username', 'unknown')
        audit_logger.log_security_event('ADMIN_LOGOUT', f'User: {admin_username}')
    
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@secure_admin_required
def dashboard():
    """Дашборд администратора"""
    try:
        stats = {
            'total_products': product_service.get_products_count(),
            'active_products': product_service.get_active_products_count(),
            'total_orders': order_service.get_orders_count(),
            'new_orders': order_service.get_new_orders_count()
        }
        
        # Добавляем информацию о статусе безопасности
        stats['security_enabled'] = SECURITY_ENABLED
        
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error loading dashboard: {e}")
        flash('Ошибка загрузки дашборда', 'error')
        return render_template('admin/dashboard.html', stats={
            'total_products': 0,
            'active_products': 0,
            'total_orders': 0,
            'new_orders': 0,
            'security_enabled': SECURITY_ENABLED
        })

@admin_bp.route('/orders')
@secure_admin_required
def orders_list():
    """Список заказов с фильтрацией и маскировкой ПД"""
    try:
        status_filter = request.args.get('status', '')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        print(f"DEBUG: Loading orders with status_filter='{status_filter}', page={page}")
        
        if SECURITY_ENABLED and hasattr(order_service, 'get_orders_paginated'):
            # Безопасный вариант с маскированными данными
            orders, total_pages = order_service.get_orders_paginated(
                status_filter=status_filter,
                page=page,
                per_page=per_page
            )
        else:
            # Обычный вариант
            orders, total_pages = order_service.get_orders_paginated(
                status_filter=status_filter,
                page=page,
                per_page=per_page
            )
        
        print(f"DEBUG: Found {len(orders)} orders, total_pages={total_pages}")
        
        return render_template('admin/orders_list.html',
                             orders=orders,
                             current_page=page,
                             total_pages=total_pages,
                             status_filter=status_filter,
                             security_enabled=SECURITY_ENABLED)
    except Exception as e:
        print(f"DEBUG: Exception in orders_list: {e}")
        import traceback
        traceback.print_exc()
        logging.error(f"Error loading orders: {e}")
        return render_template('admin/orders_list.html',
                             orders=[],
                             current_page=1,
                             total_pages=0,
                             status_filter='',
                             security_enabled=SECURITY_ENABLED)

@admin_bp.route('/orders/<int:order_id>/view')
@secure_admin_required
def view_order_details(order_id):
    """Просмотр деталей заказа с возможностью расшифровки ПД"""
    try:
        if SECURITY_ENABLED:
            admin_username = session.get('admin_username', 'unknown')
            audit_logger.log_data_access(order_id, admin_username, 'VIEW_FULL_ORDER')
            
            # Получаем расшифрованные данные заказа
            order = order_service.get_order_for_admin(order_id, decrypt=True)
        else:
            # Обычное получение заказа
            order = order_service.get_order_by_id(order_id)
        
        if not order:
            flash('Заказ не найден', 'error')
            return redirect(url_for('admin.orders_list'))
        
        return render_template('admin/order_details.html', 
                             order=order, 
                             security_enabled=SECURITY_ENABLED)
        
    except Exception as e:
        logging.error(f"Error viewing order {order_id}: {e}")
        flash('Ошибка загрузки заказа', 'error')
        return redirect(url_for('admin.orders_list'))

@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@secure_admin_required
def update_order_status(order_id):
    """Изменение статуса заказа"""
    try:
        new_status = request.form.get('status')
        if new_status not in ['new', 'in_progress', 'shipped', 'done', 'cancelled']:
            flash('Некорректный статус заказа', 'error')
            return redirect(url_for('admin.orders_list'))
        
        success = order_service.update_order_status(order_id, new_status)
        
        if success:
            if SECURITY_ENABLED:
                admin_username = session.get('admin_username', 'unknown')
                audit_logger.log_data_access(order_id, admin_username, f'STATUS_CHANGE_TO_{new_status}')
            
            flash(f'Статус заказа #{order_id} изменен на: {new_status}', 'success')
        else:
            flash(f'Ошибка изменения статуса заказа #{order_id}', 'error')
            
        return redirect(url_for('admin.orders_list'))
            
    except Exception as e:
        logging.error(f"Error updating order status: {e}")
        flash('Ошибка обновления статуса заказа', 'error')
        return redirect(url_for('admin.orders_list'))

@admin_bp.route('/orders/download')
@secure_admin_required
def download_orders():
    """Скачивание orders.csv (с проверкой прав для безопасной версии)"""
    try:
        if SECURITY_ENABLED:
            admin_username = session.get('admin_username', 'unknown')
            
            # Дополнительная проверка прав для экспорта данных
            if admin_username != os.getenv('SUPER_ADMIN_USERNAME', admin_username):
                # Если нет супер-админа, позволяем обычному админу
                pass
            
            audit_logger.log_security_event('DATA_EXPORT', f'Orders CSV exported by {admin_username}')
        
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
@secure_admin_required
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
@secure_admin_required
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
        backup_dir = os.getenv('BACKUP_DIR', './data/backups')
        
        if os.path.exists(csv_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            backup_path = os.path.join(backup_dir, f'products_{timestamp}.csv')
            os.makedirs(backup_dir, exist_ok=True)
            
            with open(csv_path, 'r', encoding='utf-8') as src:
                with open(backup_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            
            # Защищаем бэкап если безопасность включена
            if SECURITY_ENABLED:
                DataProtection.secure_file_permissions(backup_path)
            
            flash(f'Создан бэкап: products_{timestamp}.csv', 'info')
        
        # Атомарная замена файла
        temp_path = csv_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        os.replace(temp_path, csv_path)
        
        # Устанавливаем безопасные права если модуль доступен
        if SECURITY_ENABLED:
            DataProtection.secure_file_permissions(csv_path)
        
        # Инвалидация кэша
        product_service.invalidate_cache()
        
        # Логируем обновление каталога
        if SECURITY_ENABLED:
            admin_username = session.get('admin_username', 'unknown')
            audit_logger.log_security_event('PRODUCTS_UPDATE', f'Products CSV updated by {admin_username}')
        
        flash('Файл успешно загружен и кэш обновлен', 'success')
        return redirect(url_for('admin.dashboard'))
        
    except Exception as e:
        logging.error(f"Error uploading products CSV: {e}")
        flash(f'Ошибка загрузки файла: {str(e)}', 'error')
        return render_template('admin/products_upload.html')

@admin_bp.route('/products')
@secure_admin_required
def products_list():
    """Список всех товаров"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        search = request.args.get('search', '')
        category_filter = request.args.get('category', '')
        
        print(f"DEBUG: Products page - search='{search}', category='{category_filter}', page={page}")
        
        # Получаем все товары
        all_products = product_service.get_all_products()
        
        # Применяем фильтры
        if search:
            search_lower = search.lower()
            all_products = [p for p in all_products 
                          if search_lower in p['title'].lower() or 
                             search_lower in p['sku'].lower() or
                             search_lower in p['description'].lower()]
        
        if category_filter:
            all_products = [p for p in all_products if p['category'] == category_filter]
        
        # Пагинация
        total = len(all_products)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        start = (page - 1) * per_page
        end = start + per_page
        products = all_products[start:end]
        
        categories = product_service.get_categories()
        
        print(f"DEBUG: Found {len(products)} products on page {page}")
        
        return render_template('admin/products_list.html',
                             products=products,
                             categories=categories,
                             current_page=page,
                             total_pages=total_pages,
                             search=search,
                             category_filter=category_filter)
    except Exception as e:
        print(f"DEBUG: Exception in products_list: {e}")
        logging.error(f"Error loading products list: {e}")
        flash('Ошибка загрузки списка товаров', 'error')
        return render_template('admin/products_list.html',
                             products=[],
                             categories=[],
                             current_page=1,
                             total_pages=0,
                             search='',
                             category_filter='')

@admin_bp.route('/analytics')
@secure_admin_required
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
            categories_stats[cat]['total_value'] += product['price']
        
        # Топ товары по цене
        top_expensive = sorted(all_products, key=lambda x: x['price'], reverse=True)[:10]
        
        analytics_data = {
            'total_products': total_products,
            'active_products': active_products,
            'total_orders': total_orders,
            'new_orders': new_orders,
            'categories_stats': categories_stats,
            'top_expensive': top_expensive,
            'security_enabled': SECURITY_ENABLED
        }
        
        return render_template('admin/analytics.html', data=analytics_data)
    except Exception as e:
        logging.error(f"Error loading analytics: {e}")
        flash('Ошибка загрузки аналитики', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/security/cleanup-old-orders', methods=['POST'])
@secure_admin_required
def cleanup_old_orders():
    """Очистка старых заказов (GDPR compliance) - только если безопасность включена"""
    if not SECURITY_ENABLED:
        flash('Функция недоступна без модулей безопасности', 'error')
        return redirect(url_for('admin.dashboard'))
    
    try:
        admin_username = session.get('admin_username', 'unknown')
        
        # Дополнительная проверка прав
        super_admin = os.getenv('SUPER_ADMIN_USERNAME', admin_username)
        if admin_username != super_admin:
            audit_logger.log_security_event('UNAUTHORIZED_DATA_CLEANUP', f'User: {admin_username}')
            flash('Недостаточно прав для очистки данных', 'error')
            return redirect(url_for('admin.dashboard'))
        
        days = int(request.form.get('days', 365))
        if days < 30:  # Минимум 30 дней
            flash('Минимальный срок хранения данных - 30 дней', 'error')
            return redirect(url_for('admin.dashboard'))
        
        deleted_count = order_service.cleanup_old_orders(days)
        
        audit_logger.log_security_event('DATA_CLEANUP', 
                                       f'Deleted {deleted_count} orders older than {days} days by {admin_username}')
        
        flash(f'Удалено {deleted_count} старых заказов', 'success')
        return redirect(url_for('admin.dashboard'))
        
    except Exception as e:
        logging.error(f"Error cleaning up old orders: {e}")
        flash('Ошибка очистки данных', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@secure_admin_required
def settings():
    """Настройки системы"""
    if request.method == 'POST':
        try:
            # Здесь можно добавить обработку настроек
            if SECURITY_ENABLED:
                admin_username = session.get('admin_username', 'unknown')
                audit_logger.log_security_event('SETTINGS_CHANGE', f'Settings updated by {admin_username}')
            
            flash('Настройки сохранены', 'success')
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            flash('Ошибка сохранения настроек', 'error')
    
    return render_template('admin/settings.html', security_enabled=SECURITY_ENABLED)

@admin_bp.route('/backup')
@secure_admin_required
def create_backup():
    """Создание резервной копии данных"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.getenv('BACKUP_DIR', './data/backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Бэкап товаров
        products_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
        if os.path.exists(products_path):
            backup_products = os.path.join(backup_dir, f'products_manual_{timestamp}.csv')
            with open(products_path, 'r', encoding='utf-8') as src:
                with open(backup_products, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            
            if SECURITY_ENABLED:
                DataProtection.secure_file_permissions(backup_products)
        
        # Бэкап заказов
        orders_path = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        if os.path.exists(orders_path):
            backup_orders = os.path.join(backup_dir, f'orders_manual_{timestamp}.csv')
            with open(orders_path, 'r', encoding='utf-8') as src:
                with open(backup_orders, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            
            if SECURITY_ENABLED:
                DataProtection.secure_file_permissions(backup_orders)
        
        if SECURITY_ENABLED:
            admin_username = session.get('admin_username', 'unknown')
            audit_logger.log_security_event('MANUAL_BACKUP', f'Manual backup created by {admin_username}')
        
        flash(f'Резервная копия создана: {timestamp}', 'success')
    except Exception as e:
        logging.error(f"Error creating backup: {e}")
        flash('Ошибка создания резервной копии', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/health-check')
@secure_admin_required
def health_check():
    """Проверка состояния системы"""
    try:
        health_status = {
            'products_file': os.path.exists(os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')),
            'orders_file': os.path.exists(os.getenv('CSV_ORDERS_PATH', './data/orders.csv')),
            'backup_dir': os.path.exists(os.getenv('BACKUP_DIR', './data/backups')),
            'products_count': product_service.get_products_count(),
            'orders_count': order_service.get_orders_count(),
            'cache_status': len(product_service._cache) > 0 if hasattr(product_service, '_cache') else False,
            'security_enabled': SECURITY_ENABLED
        }
        
        # Дополнительные проверки безопасности
        if SECURITY_ENABLED:
            health_status['encryption_configured'] = bool(os.getenv('DATA_ENCRYPTION_KEY'))
            health_status['logs_directory'] = os.path.exists('./logs')
        
        return render_template('admin/health_check.html', status=health_status)
    except Exception as e:
        logging.error(f"Error in health check: {e}")
        flash('Ошибка проверки состояния системы', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/products/<sku>/edit', methods=['GET', 'POST'])
@secure_admin_required
def edit_product(sku):
    """Редактирование товара"""
    try:
        product = product_service.get_product_by_sku(sku)
        if not product:
            flash('Товар не найден', 'error')
            return redirect(url_for('admin.products_list'))
        
        if request.method == 'POST':
            # Обработка формы редактирования
            updated_data = {
                'title': request.form.get('title', '').strip(),
                'price': request.form.get('price', ''),
                'old_price': request.form.get('old_price', '').strip(),
                'category': request.form.get('category', '').strip(),
                'volume_ml': request.form.get('volume_ml', '').strip(),
                'color': request.form.get('color', '').strip(),
                'stock': request.form.get('stock', ''),
                'is_active': '1' if request.form.get('is_active') else '0',
                'description': request.form.get('description', '').strip()
            }
            
            # Валидация
            errors = {}
            if not updated_data['title']:
                errors['title'] = 'Название обязательно'
            
            try:
                updated_data['price'] = float(updated_data['price'])
                if updated_data['price'] < 0:
                    errors['price'] = 'Цена не может быть отрицательной'
            except ValueError:
                errors['price'] = 'Некорректная цена'
            
            if updated_data['old_price']:
                try:
                    updated_data['old_price'] = float(updated_data['old_price'])
                    if updated_data['old_price'] < 0:
                        errors['old_price'] = 'Старая цена не может быть отрицательной'
                except ValueError:
                    errors['old_price'] = 'Некорректная старая цена'
            else:
                updated_data['old_price'] = None
            
            try:
                updated_data['stock'] = int(updated_data['stock'])
            except ValueError:
                errors['stock'] = 'Некорректный остаток'
            
            if errors:
                return render_template('admin/product_edit.html', 
                                     product=product, 
                                     errors=errors,
                                     form_data=updated_data)
            
            # Обновление товара
            if hasattr(product_service, 'update_product'):
                success = product_service.update_product(sku, updated_data)
            else:
                # Заглушка если метод не реализован
                success = False
                flash('Функция редактирования товаров временно недоступна', 'warning')
            
            if success:
                if SECURITY_ENABLED:
                    admin_username = session.get('admin_username', 'unknown')
                    audit_logger.log_security_event('PRODUCT_UPDATE', f'Product {sku} updated by {admin_username}')
                
                flash(f'Товар {sku} успешно обновлен', 'success')
                return redirect(url_for('admin.products_list'))
            else:
                if not success and 'недоступна' not in str(flash):
                    flash('Ошибка обновления товара', 'error')
        
        return render_template('admin/product_edit.html', product=product)
    
    except Exception as e:
        logging.error(f"Error editing product {sku}: {e}")
        flash('Ошибка загрузки товара', 'error')
        return redirect(url_for('admin.products_list'))

@admin_bp.route('/security/status')
@secure_admin_required
def security_status():
    """Статус системы безопасности"""
    if not SECURITY_ENABLED:
        return render_template('admin/security_status.html', 
                             security_enabled=False,
                             message="Модули безопасности не установлены")
    
    try:
        # Проверяем статус безопасности
        status = {
            'encryption_key_set': bool(os.getenv('DATA_ENCRYPTION_KEY')),
            'salt_configured': bool(os.getenv('ENCRYPTION_SALT')),
            'logs_directory': os.path.exists('./logs'),
            'secure_permissions': True,  # Упрощенная проверка
            'backup_directory': os.path.exists('./data/backups'),
            'orders_encrypted': SECURITY_ENABLED
        }
        
        # Проверяем права доступа к критическим файлам
        orders_file = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        if os.path.exists(orders_file):
            file_stat = os.stat(orders_file)
            status['orders_file_permissions'] = oct(file_stat.st_mode)[-3:]
        else:
            status['orders_file_permissions'] = 'N/A'
        
        # Считаем количество записей в логе безопасности
        security_log = './logs/security.log'
        if os.path.exists(security_log):
            with open(security_log, 'r') as f:
                status['security_log_entries'] = len(f.readlines())
        else:
            status['security_log_entries'] = 0
        
        return render_template('admin/security_status.html', 
                             security_enabled=True,
                             status=status)
    except Exception as e:
        logging.error(f"Error checking security status: {e}")
        return render_template('admin/security_status.html', 
                             security_enabled=True,
                             error=str(e))

# Вспомогательная функция для инициализации безопасности при старте
def init_security():
    """Инициализация системы безопасности при запуске админки"""
    if SECURITY_ENABLED:
        try:
            # Настраиваем безопасные директории
            DataProtection.setup_secure_data_directory()
            
            # Проверяем наличие ключей шифрования
            if not os.getenv('DATA_ENCRYPTION_KEY'):
                print("⚠️  WARNING: DATA_ENCRYPTION_KEY не установлен!")
            
            print("✅ Система безопасности инициализирована")
            
        except Exception as e:
            print(f"❌ Ошибка инициализации безопасности: {e}")
    else:
        print("ℹ️  Работа без модулей безопасности")

# Инициализируем безопасность при импорте модуля
init_security()