### app/services/products.py
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
        print(f"🔍 DEBUG: Загружаем CSV из {self.csv_path}, файл существует: {os.path.exists(self.csv_path)}")
        print(f"🔍 DEBUG: Пытаемся загрузить CSV из: {self.csv_path}")
        print(f"🔍 DEBUG: Файл существует? {os.path.exists(self.csv_path)}")
        print(f"🔍 DEBUG: Текущая директория: {os.getcwd()}")

        try:
            if not os.path.exists(self.csv_path):
                print(f"❌ CSV файл не найден: {self.csv_path}")
                return

            with open(self.csv_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"🔍 DEBUG: Размер файла: {len(content)} символов")
                print(f"🔍 DEBUG: Первые 200 символов: {content[:200]}")

            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                print(f"🔍 DEBUG: Заголовки CSV: {reader.fieldnames}")

                products_count = 0
                self._cache.clear()
                self._categories_cache.clear()
                for row in reader:
                    products_count += 1
                    print(f"🔍 DEBUG: Строка {products_count}: {row}")
                    # Пример заполнения кэша и категорий
                    sku = row.get('sku')
                    if sku:
                        self._cache[sku] = {
                            'sku': sku,
                            'title': row.get('title', ''),
                            'description': row.get('description', ''),
                            'category': row.get('category', ''),
                            'price': int(row.get('price', '0')),
                            'is_active': row.get('is_active', '1') == '1'
                        }
                        self._categories_cache.add(row.get('category', ''))

                print(f"🔍 DEBUG: Всего обработано строк: {products_count}")
                print(f"🔍 DEBUG: Товаров в памяти: {len(self._cache)}")

        except Exception as e:
            print(f"❌ Ошибка при загрузке CSV: {e}")
            import traceback
            traceback.print_exc()

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

class OrderService:
    """Сервис для работы с заказами"""
    
    def __init__(self):
        self.orders = []  # Временно, пока нет БД
    
    def get_all_orders(self):
        """Получить все заказы"""
        return self.orders
    
    def get_order_by_id(self, order_id):
        """Получить заказ по ID"""
        for order in self.orders:
            if order.get('id') == order_id:
                return order
        return None
    
    def create_order(self, order_data):
        """Создать новый заказ"""
        order_id = len(self.orders) + 1
        order_data['id'] = order_id
        order_data['status'] = 'pending'
        self.orders.append(order_data)
        return order_data
    
    def update_order_status(self, order_id, status):
        """Обновить статус заказа"""
        order = self.get_order_by_id(order_id)
        if order:
            order['status'] = status
            return True
        return False