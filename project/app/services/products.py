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
                
                print(f"🔍 DEBUG: Загружаем CSV из {self.csv_path}, файл существует: {os.path.exists(self.csv_path)}")
                
                if not os.path.exists(self.csv_path):
                    self._cache = products
                    self._categories_cache = categories
                    return
                
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    # Читаем содержимое для отладки
                    content = f.read()
                    print(f"🔍 DEBUG: Первые 200 символов CSV:\n{content[:200]}")
                    
                    # Возвращаемся к началу файла
                    f.seek(0)
                    
                    reader = csv.DictReader(f)
                    print(f"🔍 DEBUG: Заголовки CSV: {reader.fieldnames}")
                    
                    row_count = 0
                    for row in reader:
                        row_count += 1
                        print(f"🔍 DEBUG: Обрабатываем строку {row_count}: {row}")
                        
                        try:
                            sku = row.get('sku', '').strip()
                            if not sku:
                                print(f"⚠️ DEBUG: Пропускаем строку {row_count} - нет SKU")
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
                            print(f"✅ DEBUG: Добавлен товар {sku}: {product['title']}")
                            
                            if product['category']:
                                categories.add(product['category'])
                                
                        except (ValueError, TypeError) as e:
                            print(f"❌ DEBUG: Ошибка в строке {row_count}: {e}")
                            continue
                
                self._cache = products
                self._categories_cache = categories
                print(f"📦 DEBUG: Загружено товаров: {len(products)}, категорий: {len(categories)}")
                
            except Exception as e:
                print(f"❌ DEBUG: Критическая ошибка загрузки CSV: {e}")
                import traceback
                traceback.print_exc()
    
    def invalidate_cache(self):
        """Инвалидация кэша и перезагрузка"""
        self._load_products()
    
    def get_all_products(self) -> List[Dict]:
        """Получение всех активных продуктов"""
        with self._lock:
            result = [p for p in self._cache.values() if p['is_active']]
            print(f"🔍 DEBUG: get_all_products возвращает {len(result)} активных товаров из {len(self._cache)} всего")
            return result
    
    def get_product_by_sku(self, sku: str) -> Optional[Dict]:
        """Получение продукта по SKU"""
        with self._lock:
            product = self._cache.get(sku)
            print(f"🔍 DEBUG: get_product_by_sku({sku}) = {product is not None}")
            return product
    
    def get_categories(self) -> List[str]:
        """Получение списка категорий"""
        with self._lock:
            return sorted(list(self._categories_cache))
    
    def get_featured_products(self, limit: int = 6) -> List[Dict]:
        """Получение рекомендуемых продуктов для главной"""
        products = self.get_all_products()
        result = products[:limit]
        print(f"🔍 DEBUG: get_featured_products возвращает {len(result)} товаров")
        for p in result:
            print(f"  - SKU: {p.get('sku')}, Title: {p.get('title')}")
        return result
    
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