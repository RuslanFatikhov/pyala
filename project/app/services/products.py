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
    
    def get_new_products(self, days: int = 30, limit: int = 4) -> List[Dict]:
        """Получение новых продуктов"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        products = self.get_all_products()
        
        new_products = []
        for product in products:
            date_added = product.get('date_added', '')
            if date_added:
                try:
                    product_date = datetime.strptime(date_added, '%Y-%m-%d')
                    if product_date >= cutoff_date:
                        new_products.append(product)
                except ValueError:
                    continue
        
        # Сортируем по дате добавления (новые сначала)
        new_products.sort(key=lambda x: x.get('date_added', ''), reverse=True)
        return new_products[:limit]
    
    def get_products_by_skus(self, skus: List[str]) -> List[Dict]:
        """Получение продуктов по списку SKU"""
        products = []
        for sku in skus:
            product = self.get_product_by_sku(sku)
            if product:
                products.append(product)
        return products
    
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
    
    def get_pialki_products(self, query: str = '', price_min: Optional[int] = None, 
                           price_max: Optional[int] = None, sort_by: str = 'default',
                           page: int = 1, per_page: int = 12) -> Tuple[List[Dict], int]:
        """Получение товаров пиалок (SKU начинается с PIA) с фильтрами и сортировкой"""
        with self._lock:
            # Фильтрация по SKU начинающемуся с PIA
            products = [p for p in self._cache.values() 
                       if p['is_active'] and p['sku'].startswith('PIA')]
            
            print(f"🔍 DEBUG: Найдено пиалок: {len(products)}")
            for p in products:
                print(f"  - {p['sku']}: {p['title']}")
            
            # Фильтрация по поиску
            if query:
                query_lower = query.lower()
                products = [p for p in products 
                           if query_lower in p['title'].lower() or 
                              query_lower in p['description'].lower() or
                              query_lower in p['color'].lower()]
            
            # Фильтрация по цене
            if price_min is not None:
                products = [p for p in products if p['price'] >= price_min]
            
            if price_max is not None:
                products = [p for p in products if p['price'] <= price_max]
            
            # Сортировка
            if sort_by == 'price_asc':
                products.sort(key=lambda x: x['price'])
            elif sort_by == 'price_desc':
                products.sort(key=lambda x: x['price'], reverse=True)
            elif sort_by == 'name':
                products.sort(key=lambda x: x['title'])
            elif sort_by == 'volume':
                products.sort(key=lambda x: int(x['volume_ml']) if x['volume_ml'].isdigit() else 0)
            # default - без сортировки, в порядке как в CSV
            
            # Пагинация
            total = len(products)
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            
            start = (page - 1) * per_page
            end = start + per_page
            products = products[start:end]
            
            return products, total_pages

    def get_pialki_stats(self) -> Dict:
        """Получение статистики по пиалкам"""
        with self._lock:
            pialki = [p for p in self._cache.values() 
                     if p['is_active'] and p['sku'].startswith('PIA')]
            
            if not pialki:
                return {
                    'total_count': 0,
                    'price_range': {'min': 0, 'max': 0},
                    'volume_range': {'min': 0, 'max': 0},
                    'colors': [],
                    'in_stock_count': 0
                }
            
            prices = [p['price'] for p in pialki]
            volumes = [int(p['volume_ml']) for p in pialki if p['volume_ml'].isdigit()]
            colors = list(set([p['color'] for p in pialki if p['color']]))
            in_stock = [p for p in pialki if p['stock'] > 0]
            
            return {
                'total_count': len(pialki),
                'price_range': {
                    'min': min(prices) if prices else 0,
                    'max': max(prices) if prices else 0
                },
                'volume_range': {
                    'min': min(volumes) if volumes else 0,
                    'max': max(volumes) if volumes else 0
                },
                'colors': sorted(colors),
                'in_stock_count': len(in_stock)
            }