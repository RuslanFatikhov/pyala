# Flask E-commerce MVP - Полная реализация

## 1. Создание структуры проекта

Скопируйте и выполните в Terminal VSCode:

```bash
# создать дерево проекта
mkdir -p project/{app/{services,templates/{admin,partials},static/{css,js,img}},data/backups}
cd project

# файлы
touch app/__init__.py app/routes_public.py app/routes_admin.py \
      app/services/{products.py,orders.py,validators.py,notify.py} \
      app/templates/{base.html,home.html,catalog.html,product.html,cart.html,checkout.html,thankyou.html} \
      app/templates/admin/{login.html,dashboard.html,products_upload.html,orders_list.html} \
      app/static/css/styles.css app/static/js/app.js \
      data/products.csv data/orders.csv \
      config.py run.py requirements.txt .env.example index.wsgi README.md

# виртуальное окружение
python3 -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# зависимости
pip install Flask python3-dotenv portalocker email-validator gunicorn
pip freeze > requirements.txt
```

## 2. Основные файлы

### app/__init__.py
```python3
from flask import Flask
from dotenv import load_dotenv
import os

def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

    from .routes_public import public_bp
    from .routes_admin import admin_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app

app = create_app()
```

### app/routes_public.py
```python3
from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for, flash
from .services.products import ProductService
from .services.orders import OrderService
from .services.validators import CheckoutValidator
from .services.notify import NotificationService
import logging

public_bp = Blueprint('public', __name__)
product_service = ProductService()
order_service = OrderService()
checkout_validator = CheckoutValidator()
notification_service = NotificationService()

@public_bp.route('/')
def home():
    """Главная страница с новинками"""
    try:
        featured_products = product_service.get_featured_products(limit=6)
        return render_template('home.html', products=featured_products)
    except Exception as e:
        logging.error(f"Error loading home page: {e}")
        return render_template('errors/500.html'), 500

@public_bp.route('/catalog')
def catalog():
    """Каталог с фильтрами и поиском"""
    try:
        # Получение параметров фильтрации
        category = request.args.get('category', '')
        q = request.args.get('q', '')
        price_min = request.args.get('price_min', type=int)
        price_max = request.args.get('price_max', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = 12

        # Получение продуктов с фильтрами
        products, total_pages = product_service.get_filtered_products(
            category=category,
            query=q,
            price_min=price_min,
            price_max=price_max,
            page=page,
            per_page=per_page
        )

        # Получение доступных категорий для фильтра
        categories = product_service.get_categories()

        return render_template('catalog.html', 
                             products=products,
                             categories=categories,
                             current_page=page,
                             total_pages=total_pages,
                             filters={
                                 'category': category,
                                 'q': q,
                                 'price_min': price_min,
                                 'price_max': price_max
                             })
    except Exception as e:
        logging.error(f"Error loading catalog: {e}")
        return render_template('errors/500.html'), 500

@public_bp.route('/product/<sku>')
def product_detail(sku):
    """Страница детализации продукта (PDP)"""
    try:
        product = product_service.get_product_by_sku(sku)
        if not product:
            return render_template('errors/404.html'), 404
        
        # Аналитика: просмотр товара
        return render_template('product.html', product=product)
    except Exception as e:
        logging.error(f"Error loading product {sku}: {e}")
        return render_template('errors/500.html'), 500

@public_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    """Добавление товара в корзину"""
    try:
        data = request.get_json()
        sku = data.get('sku')
        qty = data.get('qty', 1)

        if not sku:
            return jsonify({'error': 'SKU is required'}), 400

        # Проверка существования продукта
        product = product_service.get_product_by_sku(sku)
        if not product or not product['is_active']:
            return jsonify({'error': 'Product not found or inactive'}), 404

        # Проверка наличия
        if product['stock'] < qty:
            return jsonify({'error': 'Insufficient stock'}), 400

        # Добавление в корзину (session)
        if 'cart' not in session:
            session['cart'] = {}

        current_qty = session['cart'].get(sku, 0)
        new_qty = current_qty + qty

        if product['stock'] < new_qty:
            return jsonify({'error': 'Insufficient stock'}), 400

        session['cart'][sku] = new_qty
        session.modified = True

        # Подсчет итогов корзины
        cart_summary = _get_cart_summary()
        
        return jsonify({
            'ok': True,
            'cart_summary': cart_summary
        })
    except Exception as e:
        logging.error(f"Error adding to cart: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_bp.route('/cart/update', methods=['POST'])
def update_cart():
    """Обновление количества товара в корзине"""
    try:
        data = request.get_json()
        sku = data.get('sku')
        qty = data.get('qty', 0)

        if not sku:
            return jsonify({'error': 'SKU is required'}), 400

        if 'cart' not in session:
            session['cart'] = {}

        if qty <= 0:
            session['cart'].pop(sku, None)
        else:
            # Проверка наличия
            product = product_service.get_product_by_sku(sku)
            if product and product['stock'] >= qty:
                session['cart'][sku] = qty
            else:
                return jsonify({'error': 'Insufficient stock'}), 400

        session.modified = True
        cart_summary = _get_cart_summary()
        
        return jsonify({
            'ok': True,
            'cart_summary': cart_summary
        })
    except Exception as e:
        logging.error(f"Error updating cart: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_bp.route('/cart/remove', methods=['POST'])
def remove_from_cart():
    """Удаление товара из корзины"""
    try:
        data = request.get_json()
        sku = data.get('sku')

        if not sku:
            return jsonify({'error': 'SKU is required'}), 400

        if 'cart' in session:
            session['cart'].pop(sku, None)
            session.modified = True

        cart_summary = _get_cart_summary()
        
        return jsonify({
            'ok': True,
            'cart_summary': cart_summary
        })
    except Exception as e:
        logging.error(f"Error removing from cart: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@public_bp.route('/cart')
def cart():
    """Страница корзины"""
    try:
        cart_items = _get_cart_items()
        return render_template('cart.html', cart_items=cart_items)
    except Exception as e:
        logging.error(f"Error loading cart: {e}")
        return render_template('errors/500.html'), 500

@public_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Оформление заказа"""
    if request.method == 'GET':
        # Проверка что корзина не пуста
        if not session.get('cart'):
            flash('Корзина пуста', 'warning')
            return redirect(url_for('public.catalog'))
        
        cart_items = _get_cart_items()
        return render_template('checkout.html', cart_items=cart_items)
    
    try:
        # POST - обработка формы
        if not session.get('cart'):
            flash('Корзина пуста', 'error')
            return redirect(url_for('public.catalog'))

        # Валидация формы
        form_data = {
            'name': request.form.get('name', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'city': request.form.get('city', '').strip(),
            'address': request.form.get('address', '').strip(),
            'comment': request.form.get('comment', '').strip()
        }

        is_valid, errors = checkout_validator.validate(form_data)
        
        if not is_valid:
            cart_items = _get_cart_items()
            return render_template('checkout.html', 
                                 cart_items=cart_items,
                                 errors=errors,
                                 form_data=form_data)

        # Создание заказа
        cart_items = _get_cart_items()
        order_id = order_service.create_order(form_data, cart_items)
        
        if not order_id:
            flash('Ошибка создания заказа. Попробуйте еще раз.', 'error')
            return render_template('checkout.html', 
                                 cart_items=cart_items,
                                 form_data=form_data)

        # Отправка уведомлений
        try:
            notification_service.send_order_notification(order_id, form_data, cart_items)
        except Exception as e:
            logging.error(f"Error sending notifications for order {order_id}: {e}")

        # Очистка корзины
        session['cart'] = {}
        session.modified = True

        return redirect(url_for('public.thank_you', order_id=order_id))

    except Exception as e:
        logging.error(f"Error processing checkout: {e}")
        flash('Произошла ошибка при оформлении заказа', 'error')
        return render_template('errors/500.html'), 500

@public_bp.route('/thank-you')
def thank_you():
    """Страница благодарности после заказа"""
    order_id = request.args.get('order_id')
    return render_template('thankyou.html', order_id=order_id)

def _get_cart_summary():
    """Получение сводки корзины"""
    if not session.get('cart'):
        return {'count': 0, 'total': 0}
    
    cart_items = _get_cart_items()
    count = sum(item['qty'] for item in cart_items)
    total = sum(item['total'] for item in cart_items)
    
    return {'count': count, 'total': total}

def _get_cart_items():
    """Получение товаров корзины с деталями"""
    if not session.get('cart'):
        return []
    
    cart_items = []
    for sku, qty in session['cart'].items():
        product = product_service.get_product_by_sku(sku)
        if product and product['is_active']:
            cart_items.append({
                'product': product,
                'qty': qty,
                'total': product['price'] * qty
            })
    
    return cart_items
```

### app/routes_admin.py
```python3
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from .services.products import ProductService
from .services.orders import OrderService
from .services.validators import ProductCSVValidator
import os
import logging
from datetime import datetime

admin_bp = Blueprint('admin', __name__)
product_service = ProductService()
order_service = OrderService()
csv_validator = ProductCSVValidator()

def login_required(f):
    """Декоратор для проверки авторизации админа"""
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Авторизация администратора"""
    if request.method == 'GET':
        return render_template('admin/login.html')
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
    
    if username == admin_username and password == admin_password:
        session['admin_logged_in'] = True
        flash('Вы успешно авторизованы', 'success')
        return redirect(url_for('admin.dashboard'))
    else:
        flash('Неверные данные для входа', 'error')
        return render_template('admin/login.html')

@admin_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Выход из админки"""
    session.pop('admin_logged_in', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@login_required
def dashboard():
    """Дашборд администратора"""
    try:
        stats = {
            'total_products': product_service.get_products_count(),
            'active_products': product_service.get_active_products_count(),
            'total_orders': order_service.get_orders_count(),
            'new_orders': order_service.get_new_orders_count()
        }
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error loading dashboard: {e}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/products/download')
@login_required
def download_products():
    """Скачивание текущего products.csv"""
    try:
        csv_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
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
        
        # Атомарная замена файла
        temp_path = csv_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        os.replace(temp_path, csv_path)
        
        # Инвалидация кэша
        product_service.invalidate_cache()
        
        flash('Файл успешно загружен и кэш обновлен', 'success')
        return redirect(url_for('admin.dashboard'))
        
    except Exception as e:
        logging.error(f"Error uploading products CSV: {e}")
        flash('Ошибка загрузки файла', 'error')
        return render_template('admin/products_upload.html')

@admin_bp.route('/orders')
@login_required
def orders_list():
    """Список заказов с фильтрацией"""
    try:
        status_filter = request.args.get('status', '')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        orders, total_pages = order_service.get_orders_paginated(
            status_filter=status_filter,
            page=page,
            per_page=per_page
        )
        
        return render_template('admin/orders_list.html',
                             orders=orders,
                             current_page=page,
                             total_pages=total_pages,
                             status_filter=status_filter)
    except Exception as e:
        logging.error(f"Error loading orders: {e}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/orders/download')
@login_required
def download_orders():
    """Скачивание orders.csv"""
    try:
        csv_path = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        return send_file(csv_path, as_attachment=True, download_name='orders.csv')
    except Exception as e:
        logging.error(f"Error downloading orders CSV: {e}")
        flash('Ошибка скачивания файла', 'error')
        return redirect(url_for('admin.orders_list'))

@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    """Изменение статуса заказа"""
    try:
        new_status = request.form.get('status')
        if new_status not in ['new', 'in_progress', 'shipped', 'done', 'cancelled']:
            return jsonify({'error': 'Invalid status'}), 400
        
        success = order_service.update_order_status(order_id, new_status)
        
        if success:
            return jsonify({'ok': True})
        else:
            return jsonify({'error': 'Order not found'}), 404
            
    except Exception as e:
        logging.error(f"Error updating order status: {e}")
        return jsonify({'error': 'Internal server error'}), 500
```

### app/services/products.py
```python3
import csv
import os
import threading
from typing import List, Dict, Tuple, Optional

class ProductService:
    """Сервис для работы с продуктами"""
    
    def __init__(self):
        self.csv_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
        self._cache = {}
        self._categories_cache = set()
        self._lock = threading.RLock()
        self._load_products()
    
    def _load_products(self):
        """Загрузка продуктов из CSV в кэш"""
        with self._lock:
            try:
                products = {}
                categories = set()
                
                if not os.path.exists(self.csv_path):
                    self._cache = products
                    self._categories_cache = categories
                    return
                
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Парсинг и валидация данных
                        try:
                            sku = row.get('sku', '').strip()
                            if not sku:
                                continue
                            
                            price = float(row.get('price', 0))
                            old_price = row.get('old_price', '')
                            old_price = float(old_price) if old_price else None
                            
                            stock = int(row.get('stock', 0))
                            is_active = row.get('is_active', '0') == '1'
                            
                            # Обработка изображений
                            images = row.get('images', '').split('|')
                            images = [img.strip() for img in images if img.strip()]
                            
                            product = {
                                'sku': sku,
                                'title': row.get('title', '').strip(),
                                'price': price,
                                'old_price': old_price,
                                'category': row.get('category', '').strip(),
                                'volume_ml': row.get('volume_ml', '').strip(),
                                'color': row.get('color', '').strip(),
                                'images': images,
                                'stock': stock,
                                'is_active': is_active,
                                'description': row.get('description', '').strip()
                            }
                            
                            products[sku] = product
                            if product['category']:
                                categories.add(product['category'])
                                
                        except (ValueError, TypeError) as e:
                            continue  # Пропускаем некорректные строки
                
                self._cache = products
                self._categories_cache = categories
                
            except Exception as e:
                # В случае ошибки оставляем старый кэш
                pass
    
    def invalidate_cache(self):
        """Инвалидация кэша и перезагрузка"""
        self._load_products()
    
    def get_all_products(self) -> List[Dict]:
        """Получение всех активных продуктов"""
        with self._lock:
            return [p for p in self._cache.values() if p['is_active']]
    
    def get_product_by_sku(self, sku: str) -> Optional[Dict]:
        """Получение продукта по SKU"""
        with self._lock:
            return self._cache.get(sku)
    
    def get_categories(self) -> List[str]:
        """Получение списка категорий"""
        with self._lock:
            return sorted(list(self._categories_cache))
    
    def get_featured_products(self, limit: int = 6) -> List[Dict]:
        """Получение рекомендуемых продуктов для главной"""
        products = self.get_all_products()
        return products[:limit]
    
    def get_filtered_products(self, category: str = '', query: str = '', 
                            price_min: Optional[int] = None, price_max: Optional[int] = None,
                            page: int = 1, per_page: int = 12) -> Tuple[List[Dict], int]:
        """Получение продуктов с фильтрами и пагинацией"""
        products = self.get_all_products()
        
        # Фильтрация
        if category:
            products = [p for p in products if p['category'].lower() == category.lower()]
        
        if query:
            query_lower = query.lower()
            products = [p for p in products 
                       if query_lower in p['title'].lower() or 
                          query_lower in p['description'].lower()]
        
        if price_min is not None:
            products = [p for p in products if p['price'] >= price_min]
        
        if price_max is not None:
            products = [p for p in products if p['price'] <= price_max]
        
        # Пагинация
        total = len(products)
        total_pages = (total + per_page - 1) // per_page
        
        start = (page - 1) * per_page
        end = start + per_page
        products = products[start:end]
        
        return products, total_pages
    
    def get_products_count(self) -> int:
        """Общее количество продуктов"""
        with self._lock:
            return len(self._cache)
    
    def get_active_products_count(self) -> int:
        """Количество активных продуктов"""
        return len(self.get_all_products())
```

### app/services/orders.py
```python3
import csv
import os
import threading
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import portalocker

class OrderService:
    """Сервис для работы с заказами"""
    
    def __init__(self):
        self.csv_path = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        self._lock = threading.Lock()
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Создание CSV файла заказов если не существует"""
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['order_id', 'created_at', 'name', 'phone', 'city', 
                               'address', 'items', 'total', 'comment', 'status'])
    
    def _get_next_order_id(self) -> int:
        """Получение следующего ID заказа"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) <= 1:  # Только заголовок или пустой файл
                    return 100001
                
                # Находим максимальный ID
                max_id = 100000
                for line in lines[1:]:  # Пропускаем заголовок
                    try:
                        order_id = int(line.split(',')[0])
                        max_id = max(max_id, order_id)
                    except (ValueError, IndexError):
                        continue
                
                return max_id + 1
        except:
            return 100001
    
    def create_order(self, form_data: Dict, cart_items: List[Dict]) -> Optional[int]:
        """Создание заказа с потокобезопасной записью"""
        with self._lock:
            try:
                # Подготовка данных заказа
                order_id = self._get_next_order_id()
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
                
                # Формирование строки товаров: SKU:qty|SKU:qty
                items_str = '|'.join([f"{item['product']['sku']}:{item['qty']}" 
                                    for item in cart_items])
                
                # Подсчет общей суммы
                total = sum(item['total'] for item in cart_items)
                
                # Запись в CSV с блокировкой файла
                with open(self.csv_path, 'a', encoding='utf-8', newline='') as f:
                    portalocker.lock(f, portalocker.LOCK_EX)
                    try:
                        writer = csv.writer(f)
                        writer.writerow([
                            order_id,
                            created_at,
                            form_data['name'],
                            form_data['phone'],
                            form_data['city'],
                            form_data['address'],
                            items_str,
                            total,
                            form_data['comment'],
                            'new'
                        ])
                    finally:
                        portalocker.unlock(f)
                
                return order_id
                
            except Exception as e:
                return None
    
    def get_orders_paginated(self, status_filter: str = '', page: int = 1, 
                           per_page: int = 20) -> Tuple[List[Dict], int]:
        """Получение заказов с пагинацией и фильтрацией"""
        try:
            orders = []
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if status_filter and row.get('status') != status_filter:
                        continue
                    orders.append(row)
            
            # Сортировка по ID (новые сначала)
            orders.sort(key=lambda x: int(x.get('order_id', 0)), reverse=True)
            
            # Пагинация
            total = len(orders)
            total_pages = (total + per_page - 1) // per_page
            
            start = (page - 1) * per_page
            end = start + per_page
            orders = orders[start:end]
            
            return orders, total_pages
            
        except Exception as e:
            return [], 0
    
    def get_orders_count(self) -> int:
        """Общее количество заказов"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return max(0, len(lines) - 1)  # Минус заголовок
        except:
            return 0
    
    def get_new_orders_count(self) -> int:
        """Количество новых заказов"""
        try:
            count = 0
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status') == 'new':
                        count += 1
            return count
        except:
            return 0
    
    def update_order_status(self, order_id: int, new_status: str) -> bool:
        """Обновление статуса заказа"""
        with self._lock:
            try:
                # Чтение всех заказов
                orders = []
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        if int(row.get('order_id', 0)) == order_id:
                            row['status'] = new_status
                        orders.append(row)
                
                # Перезапись файла
                temp_path = self.csv_path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8', newline='') as f:
                    portalocker.lock(f, portalocker.LOCK_EX)
                    try:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(orders)
                    finally:
                        portalocker.unlock(f)
                
                os.replace(temp_path, self.csv_path)
                return True
                
            except Exception as e:
                return False


### app/services/validators.py
```python3
import re
from typing import Dict, List, Tuple
import csv
from io import StringIO

class CheckoutValidator:
    """Валидатор формы оформления заказа"""
    
    def __init__(self):
        self.phone_pattern = re.compile(r'^\+?[0-9\s\-\(\)]{10,15})
    
    def validate(self, form_data: Dict) -> Tuple[bool, Dict]:
        """Валидация данных формы checkout"""
        errors = {}
        
        # Имя
        name = form_data.get('name', '').strip()
        if not name:
            errors['name'] = 'Имя обязательно для заполнения'
        elif len(name) < 2:
            errors['name'] = 'Имя должно содержать минимум 2 символа'
        elif len(name) > 60:
            errors['name'] = 'Имя не должно превышать 60 символов'
        
        # Телефон
        phone = form_data.get('phone', '').strip()
        if not phone:
            errors['phone'] = 'Телефон обязателен для заполнения'
        elif not self.phone_pattern.match(phone):
            errors['phone'] = 'Некорректный формат телефона'
        
        # Город
        city = form_data.get('city', '').strip()
        if not city:
            errors['city'] = 'Город обязателен для заполнения'
        elif len(city) > 100:
            errors['city'] = 'Название города слишком длинное'
        
        # Адрес
        address = form_data.get('address', '').strip()
        if not address:
            errors['address'] = 'Адрес обязателен для заполнения'
        elif len(address) > 200:
            errors['address'] = 'Адрес слишком длинный'
        
        # Комментарий (опционально)
        comment = form_data.get('comment', '').strip()
        if len(comment) > 500:
            errors['comment'] = 'Комментарий не должен превышать 500 символов'
        
        return len(errors) == 0, errors


class ProductCSVValidator:
    """Валидатор CSV файла продуктов"""
    
    REQUIRED_COLUMNS = [
        'sku', 'title', 'price', 'old_price', 'category', 
        'volume_ml', 'color', 'images', 'stock', 'is_active', 'description'
    ]
    
    def validate_csv_content(self, content: str) -> Tuple[bool, List[str]]:
        """DRY-RUN валидация содержимого CSV"""
        errors = []
        
        try:
            # Парсинг CSV
            f = StringIO(content)
            reader = csv.DictReader(f)
            
            # Проверка заголовков
            if not reader.fieldnames:
                errors.append("CSV файл пустой или некорректный")
                return False, errors
            
            missing_columns = set(self.REQUIRED_COLUMNS) - set(reader.fieldnames)
            if missing_columns:
                errors.append(f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}")
            
            # Проверка данных
            skus = set()
            line_num = 1
            
            for row in reader:
                line_num += 1
                line_errors = []
                
                # SKU
                sku = row.get('sku', '').strip()
                if not sku:
                    line_errors.append("SKU не может быть пустым")
                elif sku in skus:
                    line_errors.append(f"Дублирующийся SKU: {sku}")
                else:
                    skus.add(sku)
                
                # Цена
                try:
                    price = float(row.get('price', 0))
                    if price < 0:
                        line_errors.append("Цена не может быть отрицательной")
                except ValueError:
                    line_errors.append("Некорректный формат цены")
                
                # Старая цена (опционально)
                old_price = row.get('old_price', '').strip()
                if old_price:
                    try:
                        old_price_val = float(old_price)
                        if old_price_val < 0:
                            line_errors.append("Старая цена не может быть отрицательной")
                    except ValueError:
                        line_errors.append("Некорректный формат старой цены")
                
                # Остаток
                try:
                    stock = int(row.get('stock', 0))
                    if stock < 0:
                        line_errors.append("Остаток не может быть отрицательным")
                except ValueError:
                    line_errors.append("Некорректный формат остатка")
                
                # Активность
                is_active = row.get('is_active', '').strip()
                if is_active not in ['0', '1']:
                    line_errors.append("is_active должно быть 0 или 1")
                
                # Название
                title = row.get('title', '').strip()
                if not title:
                    line_errors.append("Название товара не может быть пустым")
                
                if line_errors:
                    errors.append(f"Строка {line_num}: {'; '.join(line_errors)}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Ошибка парсинга CSV: {str(e)}")
            return False, errors


### app/services/notify.py
```python3
import smtplib
import requests
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List

class NotificationService:
    """Сервис уведомлений"""
    
    def __init__(self):
        self.smtp_host = os.getenv('EMAIL_SMTP_HOST')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 587))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_pass = os.getenv('EMAIL_PASS')
        self.email_to = os.getenv('EMAIL_TO')
        self.telegram_webhook = os.getenv('TELEGRAM_WEBHOOK_URL')
        self.currency = os.getenv('CURRENCY', 'RUB')
    
    def send_order_notification(self, order_id: int, form_data: Dict, cart_items: List[Dict]):
        """Отправка уведомлений о новом заказе"""
        # Email уведомление
        if self._is_email_configured():
            try:
                self._send_email_notification(order_id, form_data, cart_items)
            except Exception as e:
                logging.error(f"Error sending email notification: {e}")
        
        # Telegram уведомление
        if self.telegram_webhook:
            try:
                self._send_telegram_notification(order_id, form_data, cart_items)
            except Exception as e:
                logging.error(f"Error sending telegram notification: {e}")
    
    def _is_email_configured(self) -> bool:
        """Проверка настройки email"""
        return all([self.smtp_host, self.email_user, self.email_pass, self.email_to])
    
    def _send_email_notification(self, order_id: int, form_data: Dict, cart_items: List[Dict]):
        """Отправка email уведомления"""
        # Подсчет общей суммы
        total = sum(item['total'] for item in cart_items)
        
        # Формирование содержимого письма
        subject = f"Новый заказ #{order_id}"
        
        body = f"""
Получен новый заказ #{order_id}

Данные покупателя:
- Имя: {form_data['name']}
- Телефон: {form_data['phone']}
- Город: {form_data['city']}
- Адрес: {form_data['address']}
- Комментарий: {form_data.get('comment', 'Нет')}

Товары:
"""
        
        for item in cart_items:
            product = item['product']
            body += f"- {product['title']} x{item['qty']} = {item['total']} {self.currency}\n"
        
        body += f"\nИтого: {total} {self.currency}"
        
        # Отправка письма
        msg = MIMEMultipart()
        msg['From'] = self.email_user
        msg['To'] = self.email_to
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.email_user, self.email_pass)
            server.send_message(msg)
    
    def _send_telegram_notification(self, order_id: int, form_data: Dict, cart_items: List[Dict]):
        """Отправка Telegram уведомления"""
        total = sum(item['total'] for item in cart_items)
        
        message = f"🆕 Новый заказ #{order_id}\n\n"
        message += f"👤 {form_data['name']}\n"
        message += f"📱 {form_data['phone']}\n"
        message += f"🏙 {form_data['city']}\n"
        message += f"📍 {form_data['address']}\n\n"
        
        message += "🛍 Товары:\n"
        for item in cart_items:
            product = item['product']
            message += f"• {product['title']} x{item['qty']} = {item['total']} {self.currency}\n"
        
        message += f"\n💰 Итого: {total} {self.currency}"
        
        if form_data.get('comment'):
            message += f"\n💬 {form_data['comment']}"
        
        payload = {'text': message}
        requests.post(self.telegram_webhook, json=payload, timeout=10)


### config.py
```python3
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    
    # CSV пути
    CSV_PRODUCTS_PATH = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
    CSV_ORDERS_PATH = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
    BACKUP_DIR = os.getenv('BACKUP_DIR', './data/backups')
    
    # Админ
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
    
    # Настройки магазина
    CURRENCY = os.getenv('CURRENCY', 'RUB')
    
    # Email настройки
    EMAIL_SMTP_HOST = os.getenv('EMAIL_SMTP_HOST')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', 587))
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO')
    
    # Telegram
    TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL')


### run.py
```python3
from app import app

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)


### index.wsgi
```python3
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в python3 path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Импортируем приложение Flask
from app import app as application

if __name__ == "__main__":
    application.run()


### requirements.txt
```
Flask==2.3.3
python3-dotenv==1.0.0
portalocker==2.8.2
email-validator==2.0.0
gunicorn==21.2.0
Werkzeug==2.3.7


### .env.example
```
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
CSV_PRODUCTS_PATH=./data/products.csv
CSV_ORDERS_PATH=./data/orders.csv
BACKUP_DIR=./data/backups
CURRENCY=RUB

# Email настройки (опционально)
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
EMAIL_TO=orders@yourstore.com

# Telegram webhook (опционально)
TELEGRAM_WEBHOOK_URL=https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>


### 3. HTML Templates

### app/templates/base.html
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Керамические пиалы{% endblock %}</title>
    <link href="{{ url_for('static', filename='css/styles.css') }}" rel="stylesheet">
    <script src="{{ url_for('static', filename='js/app.js') }}" defer></script>
    
    <!-- Аналитика -->
    {% if config.get('ANALYTICS_GA4_ID') %}
    <script async src="https://www.googletagmanager.com/gtag/js?id={{ config.ANALYTICS_GA4_ID }}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', '{{ config.ANALYTICS_GA4_ID }}');
    </script>
    {% endif %}
</head>
<body>
    <header class="header">
        <nav class="container">
            <div class="nav-brand">
                <a href="{{ url_for('public.home') }}">🏺 Керамика</a>
            </div>
            <div class="nav-links">
                <a href="{{ url_for('public.catalog') }}">Каталог</a>
                <a href="{{ url_for('public.cart') }}" class="cart-link">
                    Корзина <span id="cart-count">(0)</span>
                </a>
            </div>
        </nav>
    </header>

    <main class="main">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="container">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </main>

    <footer class="footer">
        <div class="container">
            <p>&copy; 2025 Керамические пиалы. Все права защищены.</p>
        </div>
    </footer>

    <script>
        // Обновление счетчика корзины при загрузке страницы
        document.addEventListener('DOMContentLoaded', function() {
            updateCartCounter();
        });
    </script>
</body>
</html>


### app/templates/home.html
```html
{% extends "base.html" %}

{% block title %}Главная - Керамические пиалы{% endblock %}

{% block content %}
<div class="hero">
    <div class="container">
        <h1>Керамические пиалы ручной работы</h1>
        <p>Уникальные изделия для ценителей настоящего чая</p>
        <a href="{{ url_for('public.catalog') }}" class="btn btn-primary">Смотреть каталог</a>
    </div>
</div>

<section class="featured-products">
    <div class="container">
        <h2>Рекомендуемые товары</h2>
        <div class="products-grid">
            {% for product in products %}
                <div class="product-card">
                    <a href="{{ url_for('public.product_detail', sku=product.sku) }}">
                        {% if product.images %}
                            <img src="{{ product.images[0] }}" alt="{{ product.title }}" loading="lazy">
                        {% else %}
                            <div class="no-image">Нет фото</div>
                        {% endif %}
                        <h3>{{ product.title }}</h3>
                        <div class="price">
                            {% if product.old_price %}
                                <span class="old-price">{{ product.old_price }} {{ config.get('CURRENCY', 'RUB') }}</span>
                            {% endif %}
                            <span class="current-price">{{ product.price }} {{ config.get('CURRENCY', 'RUB') }}</span>
                        </div>
                    </a>
                </div>
            {% endfor %}
        </div>
    </div>
</section>
{% endblock %}


### app/templates/catalog.html
```html
{% extends "base.html" %}

{% block title %}Каталог - Керамические пиалы{% endblock %}

{% block content %}
<div class="container">
    <h1>Каталог товаров</h1>
    
    <!-- Фильтры -->
    <div class="filters">
        <form method="GET" class="filters-form">
            <div class="filter-group">
                <label>Категория:</label>
                <select name="category">
                    <option value="">Все категории</option>
                    {% for cat in categories %}
                        <option value="{{ cat }}" {% if filters.category == cat %}selected{% endif %}>
                            {{ cat }}
                        </option>
                    {% endfor %}
                </select>
            </div>
            
            <div class="filter-group">
                <label>Поиск:</label>
                <input type="text" name="q" value="{{ filters.q or '' }}" placeholder="Название товара...">
            </div>
            
            <div class="filter-group">
                <label>Цена от:</label>
                <input type="number" name="price_min" value="{{ filters.price_min or '' }}" min="0">
            </div>
            
            <div class="filter-group">
                <label>Цена до:</label>
                <input type="number" name="price_max" value="{{ filters.price_max or '' }}" min="0">
            </div>
            
            <button type="submit" class="btn btn-secondary">Применить</button>
            <a href="{{ url_for('public.catalog') }}" class="btn btn-outline">Сбросить</a>
        </form>
    </div>
    
    <!-- Товары -->
    <div class="products-grid">
        {% for product in products %}
            <div class="product-card">
                <a href="{{ url_for('public.product_detail', sku=product.sku) }}">
                    {% if product.images %}
                        <img src="{{ product.images[0] }}" alt="{{ product.title }}" loading="lazy">
                    {% else %}
                        <div class="no-image">Нет фото</div>
                    {% endif %}
                    <h3>{{ product.title }}</h3>
                    <p class="product-category">{{ product.category }}</p>
                    <div class="price">
                        {% if product.old_price %}
                            <span class="old-price">{{ product.old_price }} {{ config.get('CURRENCY', 'RUB') }}</span>
                        {% endif %}
                        <span class="current-price">{{ product.price }} {{ config.get('CURRENCY', 'RUB') }}</span>
                    </div>
                    <div class="stock-info">
                        {% if product.stock > 0 %}
                            <span class="in-stock">В наличии: {{ product.stock }}</span>
                        {% else %}
                            <span class="out-of-stock">Нет в наличии</span>
                        {% endif %}
                    </div>
                </a>
            </div>
        {% else %}
            <div class="no-products">
                <p>Товары не найдены</p>
                <a href="{{ url_for('public.catalog') }}" class="btn btn-primary">Посмотреть все товары</a>
            </div>
        {% endfor %}
    </div>
    
    <!-- Пагинация -->
    {% if total_pages > 1 %}
        <div class="pagination">
            {% for page in range(1, total_pages + 1) %}
                {% if page == current_page %}
                    <span class="page-current">{{ page }}</span>
                {% else %}
                    <a href="{{ url_for('public.catalog', page=page, **filters) }}" class="page-link">{{ page }}</a>
                {% endif %}
            {% endfor %}
        </div>
    {% endif %}
</div>
{% endblock %}


### app/templates/product.html
```html
{% extends "base.html" %}

{% block title %}{{ product.title }} - Керамические пиалы{% endblock %}

{% block content %}
<div class="container">
    <div class="product-detail">
        <div class="product-images">
            {% if product.images %}
                <div class="main-image">
                    <img id="main-product-image" src="{{ product.images[0] }}" alt="{{ product.title }}">
                </div>
                {% if product.images|length > 1 %}
                    <div class="image-thumbnails">
                        {% for image in product.images %}
                            <img src="{{ image }}" alt="{{ product.title }}" 
                                 class="thumbnail {% if loop.first %}active{% endif %}"
                                 onclick="changeMainImage('{{ image }}', this)">
                        {% endfor %}
                    </div>
                {% endif %}
            {% else %}
                <div class="no-image-large">Нет фото</div>
            {% endif %}
        </div>
        
        <div class="product-info">
            <h1>{{ product.title }}</h1>
            
            <div class="price-section">
                {% if product.old_price %}
                    <span class="old-price-large">{{ product.old_price }} {{ config.get('CURRENCY', 'RUB') }}</span>
                {% endif %}
                <span class="current-price-large">{{ product.price }} {{ config.get('CURRENCY', 'RUB') }}</span>
            </div>
            
            <div class="product-specs">
                <h3>Характеристики</h3>
                <ul>
                    {% if product.volume_ml %}
                        <li><strong>Объем:</strong> {{ product.volume_ml }} мл</li>
                    {% endif %}
                    {% if product.color %}
                        <li><strong>Цвет:</strong> {{ product.color }}</li>
                    {% endif %}
                    {% if product.category %}
                        <li><strong>Категория:</strong> {{ product.category }}</li>
                    {% endif %}
                </ul>
            </div>
            
            {% if product.description %}
                <div class="product-description">
                    <h3>Описание</h3>
                    <p>{{ product.description }}</p>
                </div>
            {% endif %}
            
            <div class="add-to-cart-section">
                {% if product.stock > 0 %}
                    <div class="quantity-selector">
                        <label for="quantity">Количество:</label>
                        <input type="number" id="quantity" value="1" min="1" max="{{ product.stock }}">
                    </div>
                    <button class="btn btn-primary btn-large" onclick="addToCart('{{ product.sku }}')">
                        Добавить в корзину
                    </button>
                    <p class="stock-info">В наличии: {{ product.stock }} шт.</p>
                {% else %}
                    <button class="btn btn-disabled btn-large" disabled>
                        Нет в наличии
                    </button>
                {% endif %}
            </div>
            
            <div class="delivery-info">
                <h3>Доставка и возврат</h3>
                <ul>
                    <li>Бесплатная доставка от 5000 {{ config.get('CURRENCY', 'RUB') }}</li>
                    <li>Доставка по России 3-7 дней</li>
                    <li>Возврат в течение 14 дней</li>
                    <li>Гарантия качества</li>
                </ul>
            </div>
        </div>
    </div>
</div>

<script>
    // Аналитика: просмотр товара
    gtag && gtag('event', 'view_item', {
        currency: '{{ config.get("CURRENCY", "RUB") }}',
        value: {{ product.price }},
        items: [{
            item_id: '{{ product.sku }}',
            item_name: '{{ product.title }}',
            category: '{{ product.category }}',
            price: {{ product.price }},
            quantity: 1
        }]
    });

    function changeMainImage(src, thumbnail) {
        document.getElementById('main-product-image').src = src;
        
        // Обновление активного thumbnail
        document.querySelectorAll('.thumbnail').forEach(t => t.classList.remove('active'));
        thumbnail.classList.add('active');
    }

    function addToCart(sku) {
        const quantity = document.getElementById('quantity').value;
        
        fetch('/cart/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sku: sku,
                qty: parseInt(quantity)
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.ok) {
                updateCartCounter();
                showNotification('Товар добавлен в корзину', 'success');
                
                // Аналитика: добавление в корзину
                gtag && gtag('event', 'add_to_cart', {
                    currency: '{{ config.get("CURRENCY", "RUB") }}',
                    value: {{ product.price }} * parseInt(quantity),
                    items: [{
                        item_id: '{{ product.sku }}',
                        item_name: '{{ product.title }}',
                        category: '{{ product.category }}',
                        price: {{ product.price }},
                        quantity: parseInt(quantity)
                    }]
                });
            } else {
                showNotification(data.error, 'error');
            }
        })
        .catch(error => {
            showNotification('Ошибка добавления товара', 'error');
        });
    }
</script>
{% endblock %}


### app/templates/cart.html
```html
{% extends "base.html" %}

{% block title %}Корзина - Керамические пиалы{% endblock %}

{% block content %}
<div class="container">
    <h1>Корзина</h1>
    
    {% if cart_items %}
        <div class="cart-items">
            {% set total = 0 %}
            {% for item in cart_items %}
                <div class="cart-item" data-sku="{{ item.product.sku }}">
                    <div class="item-image">
                        {% if item.product.images %}
                            <img src="{{ item.product.images[0] }}" alt="{{ item.product.title }}">
                        {% else %}
                            <div class="no-image">Нет фото</div>
                        {% endif %}
                    </div>
                    
                    <div class="item-info">
                        <h3>{{ item.product.title }}</h3>
                        <p class="item-price">{{ item.product.price }} {{ config.get('CURRENCY', 'RUB') }}</p>
                        {% if item.product.volume_ml %}
                            <p class="item-volume">Объем: {{ item.product.volume_ml }} мл</p>
                        {% endif %}
                    </div>
                    
                    <div class="item-quantity">
                        <label>Количество:</label>
                        <div class="quantity-controls">
                            <button onclick="updateQuantity('{{ item.product.sku }}', {{ item.qty - 1 }})">-</button>
                            <span class="quantity">{{ item.qty }}</span>
                            <button onclick="updateQuantity('{{ item.product.sku }}', {{ item.qty + 1 }})">+</button>
                        </div>
                    </div>
                    
                    <div class="item-total">
                        <span class="total-price">{{ item.total }} {{ config.get('CURRENCY', 'RUB') }}</span>
                        <button class="btn-remove" onclick="removeFromCart('{{ item.product.sku }}')">Удалить</button>
                    </div>
                </div>
                {% set total = total + item.total %}
            {% endfor %}
        </div>
        
        <div class="cart-summary">
            <div class="summary-row">
                <span>Итого:</span>
                <span class="total-amount">{{ total }} {{ config.get('CURRENCY', 'RUB') }}</span>
            </div>
            <a href="{{ url_for('public.checkout') }}" class="btn btn-primary btn-large">
                Оформить заказ
            </a>
            <a href="{{ url_for('public.catalog') }}" class="btn btn-outline">
                Продолжить покупки
            </a>
        </div>
    {% else %}
        <div class="empty-cart">
            <p>Ваша корзина пуста</p>
            <a href="{{ url_for('public.catalog') }}" class="btn btn-primary">Перейти в каталог</a>
        </div>
    {% endif %}
</div>

<script>
    function updateQuantity(sku, newQty) {
        if (newQty < 1) {
            removeFromCart(sku);
            return;
        }
        
        fetch('/cart/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sku: sku,
                qty: newQty
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.ok) {
                location.reload(); // Простое обновление страницы
            } else {
                showNotification(data.error, 'error');
            }
        });
    }
    
    function removeFromCart(sku) {
        if (!confirm('Удалить товар из корзины?')) {
            return;
        }
        
        fetch('/cart/remove', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sku: sku
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.ok) {
                location.reload();
                updateCartCounter();
            } else {
                showNotification(data.error, 'error');
            }
        });
    }
</script>
{% endblock %}


### app/templates/checkout.html
```html
{% extends "base.html" %}

{% block title %}Оформление заказа - Керамические пиалы{% endblock %}

{% block content %}
<div class="container">
    <h1>Оформление заказа</h1>
    
    <div class="checkout-layout">
        <div class="checkout-form">
            <form method="POST">
                <div class="form-group">
                    <label for="name">Имя *</label>
                    <input type="text" id="name" name="name" 
                           value="{{ form_data.name if form_data else '' }}" 
                           required maxlength="60">
                    {% if errors and errors.name %}
                        <div class="error">{{ errors.name }}</div>
                    {% endif %}
                </div>
                
                <div class="form-group">
                    <label for="phone">Телефон *</label>
                    <input type="tel" id="phone" name="phone" 
                           value="{{ form_data.phone if form_data else '' }}" 
                           required placeholder="+7 (000) 000-00-00">
                    {% if errors and errors.phone %}
                        <div class="error">{{ errors.phone }}</div>
                    {% endif %}
                </div>
                
                <div class="form-group">
                    <label for="city">Город *</label>
                    <input type="text" id="city" name="city" 
                           value="{{ form_data.city if form_data else '' }}" 
                           required maxlength="100">
                    {% if errors and errors.city %}
                        <div class="error">{{ errors.city }}</div>
                    {% endif %}
                </div>
                
                <div class="form-group">
                    <label for="address">Адрес доставки *</label>
                    <textarea id="address" name="address" 
                              required maxlength="200" rows="3">{{ form_data.address if form_data else '' }}</textarea>
                    {% if errors and errors.address %}
                        <div class="error">{{ errors.address }}</div>
                    {% endif %}
                </div>
                
                <div class="form-group">
                    <label for="comment">Комментарий к заказу</label>
                    <textarea id="comment" name="comment" 
                              maxlength="500" rows="3" placeholder="Особые пожелания, время доставки...">{{ form_data.comment if form_data else '' }}</textarea>
                    {% if errors and errors.comment %}
                        <div class="error">{{ errors.comment }}</div>
                    {% endif %}
                </div>
                
                <button type="submit" class="btn btn-primary btn-large">
                    Подтвердить заказ
                </button>
            </form>
        </div>
        
        <div class="order-summary">
            <h3>Ваш заказ</h3>
            {% set total = 0 %}
            {% for item in cart_items %}
                <div class="summary-item">
                    <span class="item-name">{{ item.product.title }}</span>
                    <span class="item-qty">x{{ item.qty }}</span>
                    <span class="item-price">{{ item.total }} {{ config.get('CURRENCY', 'RUB') }}</span>
                </div>
                {% set total = total + item.total %}
            {% endfor %}
            
            <div class="summary-total">
                <strong>Итого: {{ total }} {{ config.get('CURRENCY', 'RUB') }}</strong>
            </div>
            
            <div class="delivery-info">
                <h4>Информация о доставке</h4>
                <ul>
                    <li>Доставка 3-7 рабочих дней</li>
                    <li>Бесплатная доставка от 5000 {{ config.get('CURRENCY', 'RUB') }}</li>
                    <li>Оплата при получении</li>
                </ul>
            </div>
        </div>
    </div>
</div>

<script>
    // Аналитика: начало оформления заказа
    gtag && gtag('event', 'begin_checkout', {
        currency: '{{ config.get("CURRENCY", "RUB") }}',
        value: {{ cart_items|sum(attribute='total') }},
        items: [
            {% for item in cart_items %}
            {
                item_id: '{{ item.product.sku }}',
                item_name: '{{ item.product.title }}',
                category: '{{ item.product.category }}',
                price: {{ item.product.price }},
                quantity: {{ item.qty }}
            }{% if not loop.last %},{% endif %}
            {% endfor %}
        ]
    });

    // Аналитика при отправке формы
    document.querySelector('form').addEventListener('submit', function() {
        gtag && gtag('event', 'purchase_submit', {
            currency: '{{ config.get("CURRENCY", "RUB") }}',
            value: {{ cart_items|sum(attribute='total') }}
        });
    });
</script>
{% endblock %}


### app/templates/thankyou.html
```html
{% extends "base.html" %}

{% block title %}Спасибо за заказ - Керамические пиалы{% endblock %}

{% block content %}
<div class="container">
    <div class="thank-you-page">
        <div class="success-icon">✅</div>
        <h1>Спасибо за заказ!</h1>
        
        {% if order_id %}
            <p class="order-number">Номер вашего заказа: <strong>#{{ order_id }}</strong></p>
        {% endif %}
        
        <div class="thank-you-message">
            <p>Ваш заказ успешно принят и передан в обработку.</p>
            <p>Мы свяжемся с вами в ближайшее время для подтверждения деталей доставки.</p>
        </div>
        
        <div class="next-steps">
            <h3>Что дальше?</h3>
            <ul>
                <li>Мы обработаем ваш заказ в течение 1-2 рабочих дней</li>
                <li>Наш менеджер свяжется с вами для подтверждения</li>
                <li>Доставка осуществляется в течение 3-7 рабочих дней</li>
                <li>Оплата производится при получении товара</li>
            </ul>
        </div>
        
        <div class="action-buttons">
            <a href="{{ url_for('public.catalog') }}" class="btn btn-primary">
                Продолжить покупки
            </a>
            <a href="{{ url_for('public.home') }}" class="btn btn-outline">
                На главную
            </a>
        </div>
    </div>
</div>

<script>
    // Аналитика: успешное оформление заказа
    {% if order_id %}
    gtag && gtag('event', 'purchase_ok', {
        transaction_id: '{{ order_id }}',
        currency: '{{ config.get("CURRENCY", "RUB") }}'
    });
    {% endif %}
</script>
{% endblock %}


## 4. Admin Templates

### app/templates/admin/login.html
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в админку</title>
    <link href="{{ url_for('static', filename='css/styles.css') }}" rel="stylesheet">
</head>
<body class="admin-login-page">
    <div class="login-container">
        <h1>Администрирование</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST" class="login-form">
            <div class="form-group">
                <label for="username">Логин:</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group">
                <label for="password">Пароль:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="btn btn-primary btn-large">Войти</button>
        </form>
    </div>
</body>
</html>


### app/templates/admin/dashboard.html
```html
{% extends "admin/base.html" %}

{% block title %}Панель управления{% endblock %}

{% block content %}
<h1>Панель управления</h1>

<div class="stats-grid">
    <div class="stat-card">
        <h3>Товары</h3>
        <div class="stat-number">{{ stats.total_products }}</div>
        <div class="stat-label">Всего товаров</div>
    </div>
    
    <div class="stat-card">
        <h3>Активные товары</h3>
        <div class="stat-number">{{ stats.active_products }}</div>
        <div class="stat-label">В продаже</div>
    </div>
    
    <div class="stat-card">
        <h3>Заказы</h3>
        <div class="stat-number">{{ stats.total_orders }}</div>
        <div class="stat-label">Всего заказов</div>
    </div>
    
    <div class="stat-card">
        <h3>Новые заказы</h3>
        <div class="stat-number">{{ stats.new_orders }}</div>
        <div class="stat-label">Требуют обработки</div>
    </div>
</div>

<div class="quick-actions">
    <h2>Быстрые действия</h2>
    <div class="actions-grid">
        <a href="{{ url_for('admin.upload_products') }}" class="action-card">
            <h3>📦 Обновить товары</h3>
            <p>Загрузить новый CSV файл товаров</p>
        </a>
        
        <a href="{{ url_for('admin.orders_list') }}" class="action-card">
            <h3>📋 Заказы</h3>
            <p>Просмотр и управление заказами</p>
        </a>
        
        <a href="{{ url_for('admin.download_products') }}" class="action-card">
            <h3>⬇️ Скачать товары</h3>
            <p>Экспорт текущего файла товаров</p>
        </a>
        
        <a href="{{ url_for('admin.download_orders') }}" class="action-card">
            <h3>⬇️ Скачать заказы</h3>
            <p>Экспорт файла заказов</p>
        </a>
    </div>
</div>
{% endblock %}


### app/templates/admin/base.html
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Админка{% endblock %} - Керамические пиалы</title>
    <link href="{{ url_for('static', filename='css/styles.css') }}" rel="stylesheet">
</head>
<body class="admin-body">
    <header class="admin-header">
        <nav class="admin-nav">
            <div class="nav-brand">
                <a href="{{ url_for('admin.dashboard') }}">🏺 Админка</a>
            </div>
            <div class="nav-links">
                <a href="{{ url_for('admin.dashboard') }}">Главная</a>
                <a href="{{ url_for('admin.orders_list') }}">Заказы</a>
                <a href="{{ url_for('admin.upload_products') }}">Товары</a>
                <a href="{{ url_for('public.home') }}" target="_blank">Сайт</a>
                <form method="POST" action="{{ url_for('admin.logout') }}" style="display: inline;">
                    <button type="submit" class="btn btn-outline btn-small">Выйти</button>
                </form>
            </div>
        </nav>
    </header>

    <main class="admin-main">
        <div class="admin-container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            {% block content %}{% endblock %}
        </div>
    </main>
</body>
</html>


### app/templates/admin/products_upload.html
```html
{% extends "admin/base.html" %}

{% block title %}Загрузка товаров{% endblock %}

{% block content %}
<h1>Загрузка товаров</h1>

<div class="upload-section">
    <div class="upload-instructions">
        <h3>Инструкции по загрузке</h3>
        <ul>
            <li>Файл должен быть в формате CSV с кодировкой UTF-8</li>
            <li>Обязательные колонки: sku, title, price, old_price, category, volume_ml, color, images, stock, is_active, description</li>
            <li>SKU должны быть уникальными</li>
            <li>is_active должно быть 0 или 1</li>
            <li>Изображения разделяются символом |</li>
            <li>Перед заменой создается автоматический бэкап</li>
        </ul>
        
        <p><a href="{{ url_for('admin.download_products') }}" class="btn btn-outline">Скачать текущий файл</a></p>
    </div>
    
    {% if validation_errors %}
        <div class="validation-errors">
            <h3>Ошибки валидации</h3>
            <ul>
                {% for error in validation_errors %}
                    <li>{{ error }}</li>
                {% endfor %}
            </ul>
        </div>
    {% endif %}
    
    <form method="POST" enctype="multipart/form-data" class="upload-form">
        <div class="form-group">
            <label for="file">Выберите CSV файл:</label>
            <input type="file" id="file" name="file" accept=".csv" required>
        </div>
        
        <button type="submit" class="btn btn-primary">Загрузить и заменить</button>
        <a href="{{ url_for('admin.dashboard') }}" class="btn btn-outline">Отмена</a>
    </form>
</div>

<div class="csv-example">
    <h3>Пример CSV файла</h3>
    <pre>sku,title,price,old_price,category,volume_ml,color,images,stock,is_active,description
PIA-001,Пиала целадон 90 мл,5990,,пиалы,90,зелёный,"/static/img/pia001_1.jpg|/static/img/pia001_2.jpg",3,1,"Глазурь целадон"
PIA-002,Матовая тёмная 70 мл,7990,8990,пиалы,70,чёрный,"https://cdn.site/pia002.jpg",1,1,"Фактурная поверхность"</pre>
</div>
{% endblock %}


### app/templates/admin/orders_list.html
```html
{% extends "admin/base.html" %}

{% block title %}Заказы{% endblock %}

{% block content %}
<h1>Заказы</h1>

<div class="orders-controls">
    <form method="GET" class="filter-form">
        <label>Статус:</label>
        <select name="status" onchange="this.form.submit()">
            <option value="">Все статусы</option>
            <option value="new" {% if status_filter == 'new' %}selected{% endif %}>Новые</option>
            <option value="in_progress" {% if status_filter == 'in_progress' %}selected{% endif %}>В обработке</option>
            <option value="shipped" {% if status_filter == 'shipped' %}selected{% endif %}>Отправлены</option>
            <option value="done" {% if status_filter == 'done' %}selected{% endif %}>Выполнены</option>
            <option value="cancelled" {% if status_filter == 'cancelled' %}selected{% endif %}>Отменены</option>
        </select>
    </form>
    
    <a href="{{ url_for('admin.download_orders') }}" class="btn btn-outline">Экспорт CSV</a>
</div>

<div class="orders-table">
    <table>
        <thead>
            <tr>
                <th>№ заказа</th>
                <th>Дата</th>
                <th>Клиент</th>
                <th>Телефон</th>
                <th>Город</th>
                <th>Товары</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Действия</th>
            </tr>
        </thead>
        <tbody>
            {% for order in orders %}
                <tr>
                    <td>{{ order.order_id }}</td>
                    <td>{{ order.created_at }}</td>
                    <td>{{ order.name }}</td>
                    <td>{{ order.phone }}</td>
                    <td>{{ order.city }}</td>
                    <td class="items-cell">
                        {% for item in order.items.split('|') %}
                            {% set sku, qty = item.split(':') %}
                            <div>{{ sku }} x{{ qty }}</div>
                        {% endfor %}
                    </td>
                    <td>{{ order.total }} {{ config.get('CURRENCY', 'RUB') }}</td>
                    <td>
                        <span class="status status-{{ order.status }}">
                            {% if order.status == 'new' %}Новый
                            {% elif order.status == 'in_progress' %}В обработке
                            {% elif order.status == 'shipped' %}Отправлен
                            {% elif order.status == 'done' %}Выполнен
                            {% elif order.status == 'cancelled' %}Отменен
                            {% else %}{{ order.status }}
                            {% endif %}
                        </span>
                    </td>
                    <td>
                        <form method="POST" action="{{ url_for('admin.update_order_status', order_id=order.order_id) }}" class="status-form">
                            <select name="status" onchange="this.form.submit()">
                                <option value="new" {% if order.status == 'new' %}selected{% endif %}>Новый</option>
                                <option value="in_progress" {% if order.status == 'in_progress' %}selected{% endif %}>В обработке</option>
                                <option value="shipped" {% if order.status == 'shipped' %}selected{% endif %}>Отправлен</option>
                                <option value="done" {% if order.status == 'done' %}selected{% endif %}>Выполнен</option>
                                <option value="cancelled" {% if order.status == 'cancelled' %}selected{% endif %}>Отменен</option>
                            </select>
                        </form>
                    </td>
                </tr>
            {% else %}
                <tr>
                    <td colspan="9" class="no-orders">Заказы не найдены</td>
                </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

{% if total_pages > 1 %}
    <div class="pagination">
        {% for page in range(1, total_pages + 1) %}
            {% if page == current_page %}
                <span class="page-current">{{ page }}</span>
            {% else %}
                <a href="{{ url_for('admin.orders_list', page=page, status=status_filter) }}" class="page-link">{{ page }}</a>
            {% endif %}
        {% endfor %}
    </div>
{% endif %}
{% endblock %}


## 5. Error Templates

### app/templates/errors/404.html
```html
{% extends "base.html" %}

{% block title %}Страница не найдена{% endblock %}

{% block content %}
<div class="container">
    <div class="error-page">
        <h1>404</h1>
        <h2>Страница не найдена</h2>
        <p>Запрашиваемая страница не существует или была перемещена.</p>
        <a href="{{ url_for('public.home') }}" class="btn btn-primary">На главную</a>
        <a href="{{ url_for('public.catalog') }}" class="btn btn-outline">В каталог</a>
    </div>
</div>
{% endblock %}


### app/templates/errors/500.html
```html
{% extends "base.html" %}

{% block title %}Ошибка сервера{% endblock %}

{% block content %}
<div class="container">
    <div class="error-page">
        <h1>500</h1>
        <h2>Внутренняя ошибка сервера</h2>
        <p>Произошла техническая ошибка. Мы уже работаем над её устранением.</p>
        <p>Попробуйте обновить страницу через несколько минут.</p>
        <a href="{{ url_for('public.home') }}" class="btn btn-primary">На главную</a>
    </div>
</div>
{% endblock %}


## 6. Static Files

### app/static/css/styles.css
```css
/* Reset и базовые стили */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f9f9f9;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}

/* Header */
.header {
    background: #fff;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    position: sticky;
    top: 0;
    z-index: 100;
}

.header nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 0;
}

.nav-brand a {
    font-size: 1.5rem;
    font-weight: bold;
    text-decoration: none;
    color: #8B4513;
}

.nav-links {
    display: flex;
    gap: 2rem;
    align-items: center;
}

.nav-links a {
    text-decoration: none;
    color: #666;
    font-weight: 500;
    transition: color 0.2s;
}

.nav-links a:hover {
    color: #8B4513;
}

.cart-link {
    position: relative;
}

#cart-count {
    background: #e74c3c;
    color: white;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 0.8rem;
    margin-left: 5px;
}

/* Main content */
.main {
    min-height: calc(100vh - 200px);
    padding: 2rem 0;
}

/* Hero section */
.hero {
    background: linear-gradient(135deg, #8B4513, #D2691E);
    color: white;
    text-align: center;
    padding: 4rem 0;
    margin-bottom: 3rem;
}

.hero h1 {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.hero p {
    font-size: 1.2rem;
    margin-bottom: 2rem;
}

/* Buttons */
.btn {
    display: inline-block;
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 5px;
    text-decoration: none;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
}

.btn-primary {
    background: #8B4513;
    color: white;
}

.btn-primary:hover {
    background: #6B3410;
}

.btn-secondary {
    background: #666;
    color: white;
}

.btn-outline {
    background: transparent;
    border: 2px solid #8B4513;
    color: #8B4513;
}

.btn-outline:hover {
    background: #8B4513;
    color: white;
}

.btn-large {
    padding: 1rem 2rem;
    font-size: 1.1rem;
}

.btn-small {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
}

.btn-disabled {
    background: #ccc;
    color: #999;
    cursor: not-allowed;
}

.btn-remove {
    background: #e74c3c;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 3px;
    cursor: pointer;
}

/* Products grid */
.products-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 2rem;
    margin: 2rem 0;
}

.product-card {
    background: white;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}

.product-card:hover {
    transform: translateY(-5px);
}

.product-card img {
    width: 100%;
    height: 200px;
    object-fit: cover;
}

.no-image {
    width: 100%;
    height: 200px;
    background: #f0f0f0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #999;
}

.product-card h3 {
    padding: 1rem;
    font-size: 1.1rem;
}

.product-category {
    padding: 0 1rem;
    color: #666;
    font-size: 0.9rem;
}

.price {
    padding: 0 1rem 1rem;
}

.old-price {
    text-decoration: line-through;
    color: #999;
    margin-right: 0.5rem;
}

.current-price {
    font-weight: bold;
    color: #8B4513;
}

.stock-info {
    padding: 0 1rem 1rem;
    font-size: 0.9rem;
}

.in-stock {
    color: #27ae60;
}

.out-of-stock {
    color: #e74c3c;
}

/* Filters */
.filters {
    background: white;
    padding: 1.5rem;
    border-radius: 10px;
    margin-bottom: 2rem;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.filters-form {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    align-items: end;
}

.filter-group {
    display: flex;
    flex-direction: column;
    min-width: 150px;
}

.filter-group label {
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.filter-group input,
.filter-group select {
    padding: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 5px;
}

/* Product detail */
.product-detail {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.product-images img {
    width: 100%;
    border-radius: 10px;
}

.image-thumbnails {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
}

.thumbnail {
    width: 80px;
    height: 80px;
    object-fit: cover;
    border-radius: 5px;
    cursor: pointer;
    opacity: 0.7;
    transition: opacity 0.2s;
}

.thumbnail.active,
.thumbnail:hover {
    opacity: 1;
}

.no-image-large {
    width: 100%;
    height: 400px;
    background: #f0f0f0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #999;
    border-radius: 10px;
}

.price-section {
    margin: 1rem 0;
}

.old-price-large {
    text-decoration: line-through;
    color: #999;
    font-size: 1.2rem;
    margin-right: 1rem;
}

.current-price-large {
    font-size: 2rem;
    font-weight: bold;
    color: #8B4513;
}

.product-specs,
.product-description {
    margin: 2rem 0;
}

.product-specs ul {
    list-style: none;
}

.product-specs li {
    padding: 0.5rem 0;
    border-bottom: 1px solid #eee;
}

.add-to-cart-section {
    margin: 2rem 0;
}

.quantity-selector {
    margin-bottom: 1rem;
}

.quantity-selector input {
    width: 80px;
    padding: 0.5rem;
    margin-left: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 5px;
}

.delivery-info {
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 10px;
    margin-top: 2rem;
}

.delivery-info ul {
    list-style: none;
}

.delivery-info li {
    padding: 0.3rem 0;
    color: #666;
}

/* Cart */
.cart-items {
    background: white;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    margin-bottom: 2rem;
}

.cart-item {
    display: grid;
    grid-template-columns: 100px 1fr auto auto;
    gap: 1rem;
    padding: 1.5rem;
    border-bottom: 1px solid #eee;
    align-items: center;
}

.cart-item:last-child {
    border-bottom: none;
}

.item-image img {
    width: 100px;
    height: 100px;
    object-fit: cover;
    border-radius: 5px;
}

.item-info h3 {
    margin-bottom: 0.5rem;
}

.item-price {
    color: #666;
    margin-bottom: 0.5rem;
}

.item-volume {
    color: #999;
    font-size: 0.9rem;
}

.quantity-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.quantity-controls button {
    width: 30px;
    height: 30px;
    border: 1px solid #ddd;
    background: white;
    cursor: pointer;
    border-radius: 3px;
}

.quantity-controls .quantity {
    padding: 0 1rem;
    font-weight: bold;
}

.item-total {
    text-align: right;
}

.total-price {
    font-weight: bold;
    font-size: 1.1rem;
    color: #8B4513;
    display: block;
    margin-bottom: 0.5rem;
}

.cart-summary {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    text-align: center;
}

.summary-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 1rem;
    font-size: 1.2rem;
}

.total-amount {
    font-weight: bold;
    color: #8B4513;
}

.empty-cart {
    text-align: center;
    padding: 3rem;
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

/* Checkout */
.checkout-layout {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 3rem;
}

.checkout-form {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.form-group {
    margin-bottom: 1.5rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.form-group input,
.form-group textarea,
.form-group select {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 5px;
    font-size: 1rem;
}

.form-group textarea {
    resize: vertical;
}

.error {
    color: #e74c3c;
    font-size: 0.9rem;
    margin-top: 0.25rem;
}

.order-summary {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    height: fit-content;
}

.summary-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid #eee;
}

.summary-item:last-child {
    border-bottom: none;
}

.item-name {
    flex: 1;
}

.item-qty {
    margin: 0 1rem;
    color: #666;
}

.summary-total {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 2px solid #8B4513;
    font-size: 1.2rem;
}

/* Thank you page */
.thank-you-page {
    text-align: center;
    background: white;
    padding: 3rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    max-width: 600px;
    margin: 0 auto;
}

.success-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
}

.order-number {
    font-size: 1.2rem;
    color: #8B4513;
    margin-bottom: 2rem;
}

.thank-you-message {
    margin: 2rem 0;
}

.next-steps {
    text-align: left;
    margin: 2rem 0;
}

.next-steps ul {
    list-style: none;
}

.next-steps li {
    padding: 0.5rem 0;
    padding-left: 1rem;
    position: relative;
}

.next-steps li:before {
    content: "✓";
    position: absolute;
    left: 0;
    color: #27ae60;
}

.action-buttons {
    margin-top: 2rem;
}

.action-buttons .btn {
    margin: 0 0.5rem;
}

/* Alerts */
.alert {
    padding: 1rem;
    border-radius: 5px;
    margin-bottom: 1rem;
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

.alert-warning {
    background: #fff3cd;
    color: #856404;
    border: 1px solid #ffeaa7;
}

.alert-info {
    background: #d1ecf1;
    color: #0c5460;
    border: 1px solid #bee5eb;
}

/* Pagination */
.pagination {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    margin: 2rem 0;
}

.page-link,
.page-current {
    padding: 0.5rem 1rem;
    border: 1px solid #ddd;
    text-decoration: none;
    color: #666;
    border-radius: 5px;
}

.page-link:hover {
    background: #f8f9fa;
}

.page-current {
    background: #8B4513;
    color: white;
    border-color: #8B4513;
}

/* Admin styles */
.admin-body {
    background: #f4f4f4;
}

.admin-header {
    background: #2c3e50;
    color: white;
}

.admin-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 0;
}

.admin-nav .nav-brand a {
    color: white;
}

.admin-nav .nav-links a {
    color: #ecf0f1;
    margin-right: 1rem;
}

.admin-nav .nav-links a:hover {
    color: white;
}

.admin-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem 20px;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
    margin-bottom: 3rem;
}

.stat-card {
    background: white;
    padding: 1.5rem;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    text-align: center;
}

.stat-number {
    font-size: 2.5rem;
    font-weight: bold;
    color: #8B4513;
    margin: 0.5rem 0;
}

.stat-label {
    color: #666;
    font-size: 0.9rem;
}

.actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
}

.action-card {
    background: white;
    padding: 1.5rem;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    text-decoration: none;
    color: inherit;
    transition: transform 0.2s;
}

.action-card:hover {
    transform: translateY(-2px);
}

.action-card h3 {
    margin-bottom: 0.5rem;
}

.action-card p {
    color: #666;
    font-size: 0.9rem;
}

/* Admin login */
.admin-login-page {
    background: linear-gradient(135deg, #2c3e50, #34495e);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}

.login-container {
    background: white;
    padding: 3rem;
    border-radius: 10px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    width: 100%;
    max-width: 400px;
}

.login-form .form-group {
    margin-bottom: 1.5rem;
}

/* Admin tables */
.orders-table {
    background: white;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    margin: 2rem 0;
}

.orders-table table {
    width: 100%;
    border-collapse: collapse;
}

.orders-table th,
.orders-table td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid #eee;
}

.orders-table th {
    background: #f8f9fa;
    font-weight: 600;
}

.items-cell {
    max-width: 200px;
}

.items-cell div {
    font-size: 0.9rem;
    color: #666;
}

.status {
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 500;
}

.status-new {
    background: #fff3cd;
    color: #856404;
}

.status-in_progress {
    background: #d1ecf1;
    color: #0c5460;
}

.status-shipped {
    background: #d4edda;
    color: #155724;
}

.status-done {
    background: #d1f2eb;
    color: #00695c;
}

.status-cancelled {
    background: #f8d7da;
    color: #721c24;
}

.status-form select {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
    border: 1px solid #ddd;
    border-radius: 3px;
}

.orders-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.filter-form {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.no-orders {
    text-align: center;
    color: #666;
    padding: 2rem;
}

/* Upload forms */
.upload-section {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    margin-bottom: 2rem;
}

.upload-instructions {
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 5px;
    margin-bottom: 2rem;
}

.upload-instructions ul {
    margin: 1rem 0;
    padding-left: 1.5rem;
}

.validation-errors {
    background: #f8d7da;
    color: #721c24;
    padding: 1.5rem;
    border-radius: 5px;
    margin-bottom: 2rem;
}

.validation-errors ul {
    margin: 1rem 0;
    padding-left: 1.5rem;
}

.upload-form {
    margin: 2rem 0;
}

.csv-example {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.csv-example pre {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 5px;
    overflow-x: auto;
    font-size: 0.8rem;
}

/* Error pages */
.error-page {
    text-align: center;
    padding: 3rem;
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    max-width: 600px;
    margin: 0 auto;
}

.error-page h1 {
    font-size: 6rem;
    color: #8B4513;
    margin-bottom: 1rem;
}

.error-page h2 {
    margin-bottom: 1rem;
}

.error-page p {
    margin-bottom: 2rem;
    color: #666;
}

/* Footer */
.footer {
    background: #2c3e50;
    color: white;
    text-align: center;
    padding: 2rem 0;
    margin-top: 3rem;
}

/* Responsive */
@media (max-width: 768px) {
    .container {
        padding: 0 15px;
    }
    
    .header nav {
        flex-direction: column;
        gap: 1rem;
    }
    
    .nav-links {
        gap: 1rem;
    }
    
    .hero h1 {
        font-size: 2rem;
    }
    
    .products-grid {
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 1rem;
    }
    
    .product-detail {
        grid-template-columns: 1fr;
        gap: 2rem;
    }
    
    .filters-form {
        flex-direction: column;
        align-items: stretch;
    }
    
    .filter-group {
        min-width: auto;
    }
    
    .cart-item {
        grid-template-columns: 80px 1fr;
        gap: 1rem;
    }
    
    .item-quantity,
    .item-total {
        grid-column: 1 / -1;
        margin-top: 1rem;
    }
    
    .checkout-layout {
        grid-template-columns: 1fr;
        gap: 2rem;
    }
    
    .stats-grid {
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }
    
    .actions-grid {
        grid-template-columns: 1fr;
    }
    
    .orders-table {
        overflow-x: auto;
    }
    
    .orders-table table {
        min-width: 800px;
    }
}

@media (max-width: 480px) {
    .hero {
        padding: 2rem 0;
    }
    
    .hero h1 {
        font-size: 1.5rem;
    }
    
    .products-grid {
        grid-template-columns: 1fr;
    }
    
    .btn-large {
        width: 100%;
    }
}

/* Утилитарные классы */
.text-center { text-align: center; }
.text-right { text-align: right; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-3 { margin-bottom: 1.5rem; }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mt-3 { margin-top: 1.5rem; }


### app/static/js/app.js
```javascript
// Глобальные функции для работы с корзиной и уведомлениями

// Обновление счетчика корзины
function updateCartCounter() {
    fetch('/cart')
        .then(response => response.text())
        .then(html => {
            // Простой способ извлечь количество товаров из HTML
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const cartItems = doc.querySelectorAll('.cart-item');
            const count = cartItems.length;
            
            const counter = document.getElementById('cart-count');
            if (counter) {
                counter.textContent = `(${count})`;
            }
        })
        .catch(error => {
            console.error('Error updating cart counter:', error);
        });
}

// Показ уведомлений
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} notification`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        opacity: 0;
        transform: translateY(-20px);
        transition: all 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateY(0)';
    }, 100);
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// Добавление товара в корзину (универсальная функция)
function addToCart(sku, qty = 1) {
    fetch('/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            sku: sku,
            qty: qty
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            updateCartCounter();
            showNotification('Товар добавлен в корзину', 'success');
            
            // Аналитика для GA4
            if (typeof gtag !== 'undefined') {
                gtag('event', 'add_to_cart', {
                    currency: 'RUB',
                    value: data.cart_summary.total,
                    items: [{
                        item_id: sku,
                        quantity: qty
                    }]
                });
            }
        } else {
            showNotification(data.error || 'Ошибка добавления товара', 'error');
        }
    })
    .catch(error => {
        console.error('Error adding to cart:', error);
        showNotification('Ошибка добавления товара', 'error');
    });
}

// Ленивая загрузка изображений
document.addEventListener('DOMContentLoaded', function() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
});

// Обработка форм с AJAX (опционально)
function submitFormAjax(formElement, successCallback) {
    const formData = new FormData(formElement);
    
    fetch(formElement.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (successCallback) {
                successCallback(data);
            }
            showNotification(data.message || 'Успешно выполнено', 'success');
        } else {
            showNotification(data.error || 'Произошла ошибка', 'error');
        }
    })
    .catch(error => {
        console.error('Form submission error:', error);
        showNotification('Ошибка отправки формы', 'error');
    });
}

// Маска для телефона (простая)
document.addEventListener('DOMContentLoaded', function() {
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length > 0) {
                if (value[0] === '8') {
                    value = '7' + value.substring(1);
                }
                if (value[0] === '7') {
                    value = value.substring(0, 11);
                    const formatted = value.replace(/(\d{1})(\d{3})(\d{3})(\d{2})(\d{2})/, '+$1 ($2) $3-$4-$5');
                    e.target.value = formatted;
                }
            }
        });
    });
});


## 7. Data Files

### data/products.csv
```csv
sku,title,price,old_price,category,volume_ml,color,images,stock,is_active,description
PIA-001,Пиала целадон 90 мл,5990,,пиалы,90,зелёный,"/static/img/pia001_1.jpg|/static/img/pia001_2.jpg",5,1,"Классическая пиала с глазурью целадон. Идеальна для чайной церемонии."
PIA-002,Матовая тёмная 70 мл,7990,8990,пиалы,70,чёрный,"/static/img/pia002_1.jpg",3,1,"Современная пиала с матовой фактурной поверхностью."
PIA-003,Белая фарфоровая 80 мл,4990,,пиалы,80,белый,"/static/img/pia003_1.jpg|/static/img/pia003_2.jpg|/static/img/pia003_3.jpg",8,1,"Классический белый фарфор высокого качества."
PIA-004,Синяя с узором 75 мл,6990,,пиалы,75,синий,"/static/img/pia004_1.jpg",2,1,"Традиционная роспись кобальтом под глазурью."
PIA-005,Коричневая глиняная 100 мл,3990,,пиалы,100,коричневый,"/static/img/pia005_1.jpg",0,1,"Неглазурованная глиняная пиала ручной работы."
SET-001,Набор из 4 пиал,19990,22990,наборы,,разноцветный,"/static/img/set001_1.jpg|/static/img/set001_2.jpg",3,1,"Подарочный набор из четырех разных пиал в красивой упаковке."

ю
### data/orders.csv
```csv
order_id,created_at,name,phone,city,address,items,total,comment,status


## 8. README.md
```markdown
# MVP Интернет-магазин керамических пиал

Минимально жизнеспособный интернет-магазин на Flask с хранением данных в CSV файлах.

## Возможности

- 📦 Каталог товаров с фильтрами и поиском
- 🛒 Корзина покупок
- 📝 Оформление заказов
- 📧 Email и Telegram уведомления
- 👨‍💼 Админ-панель для управления
- 📊 Аналитика событий
- 📱 Адаптивный дизайн

## Быстрый старт

### 1. Создание структуры проекта

Скопируйте и выполните в Terminal VSCode:

```bash
# создать дерево проекта
mkdir -p project/{app/{services,templates/{admin,partials},static/{css,js,img}},data/backups}
cd project

# файлы
touch app/__init__.py app/routes_public.py app/routes_admin.py \
      app/services/{products.py,orders.py,validators.py,notify.py} \
      app/templates/{base.html,home.html,catalog.html,product.html,cart.html,checkout.html,thankyou.html} \
      app/templates/admin/{login.html,dashboard.html,products_upload.html,orders_list.html} \
      app/static/css/styles.css app/static/js/app.js \
      data/products.csv data/orders.csv \
      config.py run.py requirements.txt .env.example index.wsgi README.md

# виртуальное окружение
python3 -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# зависимости
pip install Flask python3-dotenv portalocker email-validator gunicorn
pip freeze > requirements.txt
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
```
SECRET_KEY=your-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
# ... остальные настройки
```

### 3. Локальный запуск

```bash
# Разработка
python3 run.py

# Продакшн-режим локально
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Откройте http://localhost:5000 (или http://localhost:8000 для gunicorn)

## Структура проекта

```
project/
├── app/
│   ├── __init__.py              # Инициализация Flask приложения
│   ├── routes_public.py         # Публичные маршруты (каталог, корзина, заказы)
│   ├── routes_admin.py          # Админ маршруты
│   ├── services/
│   │   ├── products.py          # Работа с товарами (CSV кэш)
│   │   ├── orders.py            # Работа с заказами (потокобезопасная запись)
│   │   ├── validators.py        # Валидация форм и CSV
│   │   └── notify.py            # Email/Telegram уведомления
│   ├── templates/               # HTML шаблоны
│   └── static/                  # CSS, JS, изображения
├── data/
│   ├── products.csv             # База товаров
│   ├── orders.csv              # Заказы
│   └── backups/                # Автобэкапы при обновлении
├── config.py                   # Конфигурация
├── run.py                      # Запуск разработки
├── index.wsgi                  # Точка входа для WSGI серверов
└── requirements.txt            # Зависимости python3
```

## Админ-панель

Доступ: `/admin`

Возможности:
- Просмотр статистики
- Загрузка нового CSV товаров с валидацией
- Управление заказами
- Экспорт данных

## Формат данных

### products.csv
```csv
sku,title,price,old_price,category,volume_ml,color,images,stock,is_active,description
PIA-001,Пиала целадон 90 мл,5990,,пиалы,90,зелёный,"/static/img/pia001_1.jpg|/static/img/pia001_2.jpg",5,1,"Описание товара"
```

### orders.csv
```csv
order_id,created_at,name,phone,city,address,items,total,comment,status
100001,2025-08-10 14:22,Имя,+7...,Город,Адрес,"PIA-001:2|PIA-002:1",19970,"Комментарий",new
```

## Деплой на Timeweb

### 1. Подготовка файлов

Убедитесь что есть:
- `index.wsgi` - точка входа WSGI
- `.env` с производственными настройками
- `requirements.txt` с зависимостями

### 2. Загрузка на сервер

Загрузите проект в корневую папку через Git/SFTP.

### 3. Настройка в панели Timeweb

1. Выберите python3 3.10+
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Убедитесь что точка входа: `index.wsgi`
4. Настройте права на запись для папки `data/`:
   ```bash
   chmod -R 755 data
   ```

### 4. Проверка

Откройте `https://yourdomain.com/health` - должно вернуть `{"ok": true}`

## Особенности реализации

### Потокобезопасность
- Запись заказов с file locking (`portalocker`)
- Thread-safe кэш товаров с RLock

### Кэширование
- Товары кэшируются в памяти
- Автоматическая инвалидация при обновлении CSV

### Валидация
- DRY-RUN проверка CSV перед заменой
- Серверная валидация всех форм

### Безопасность
- CSRF защита админки
- Валидация размеров файлов
- Санитизация пользовательского ввода

## Аналитика

Поддерживаемые события:
- `view_item` - просмотр товара
- `add_to_cart` - добавление в корзину  
- `begin_checkout` - начало оформления
- `purchase_submit` - отправка заказа
- `purchase_ok` - успешный заказ

Для подключения GA4 добавьте в `.env`:
```
ANALYTICS_GA4_ID=G-XXXXXXXXXX
```

## Уведомления

### Email
Настройте SMTP в `.env`:
```
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
EMAIL_TO=orders@yourstore.com
```

### Telegram
Получите webhook URL и добавьте в `.env`:
```
TELEGRAM_WEBHOOK_URL=https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>
```

## Разработка

### Добавление товаров
1. Отредактируйте `data/products.csv`
2. Или загрузите через админку `/admin/products/upload`

### Тестирование заказов
1. Добавьте товары в корзину
2. Оформите заказ
3. Проверьте `data/orders.csv`
4. Проверьте уведомления

### Расширение функционала
- Модифицируйте `app/services/` для логики
- Добавьте маршруты в `routes_public.py` / `routes_admin.py`
- Обновите шаблоны в `templates/`

## Требования

- python3 3.10+
- Flask 2.3+
- Права на запись в папку `data/`

## Лицензия

MIT License - свободно используйте для коммерческих проектов.
```

## 9. Финальная проверка

### Тест-кейсы для проверки:

1. **Каталог и поиск**
   ```bash
   curl http://localhost:5000/catalog?q=пиала
   curl http://localhost:5000/catalog?category=пиалы&price_min=5000
   ```

2. **Добавление в корзину**
   ```bash
   curl -X POST http://localhost:5000/cart/add \
        -H "Content-Type: application/json" \
        -d '{"sku":"PIA-001","qty":2}'
   ```

3. **Админ доступ**
   - Откройте `/admin`
   - Войдите (admin/admin)
   - Попробуйте загрузить CSV

4. **Health check**
   ```bash
   curl http://localhost:5000/health
   # Должно вернуть: {"ok": true}
   ```

### Checklist деплоя:

- [ ] `index.wsgi` корректно импортирует `app as application`
- [ ] `.env` содержит все необходимые переменные
- [ ] `requirements.txt` установлен на сервере  
- [ ] Права на запись для `data/` настроены
- [ ] CSV файлы созданы и корректны
- [ ] Email/Telegram уведомления настроены (опционально)
- [ ] `/health` возвращает OK

Проект готов к использованию! 🎉