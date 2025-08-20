### app/routes_public.py
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

