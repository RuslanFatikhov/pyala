# app/services/product_service.py
import csv
import os
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

class ProductService:
    """Сервис для работы с продуктами с автопоиском изображений"""
    
    def __init__(self):
        self.csv_path = os.getenv('CSV_PRODUCTS_PATH', './data/products.csv')
        self._cache = {}
        self._categories_cache = set()
        self._lock = threading.RLock()
        self._load_products()
    
    def find_product_images(self, sku: str, max_images: int = 10) -> List[str]:
        """
        Автоматически находит изображения товара по SKU
        Ищет файлы вида: SKU_1.jpg, SKU_2.jpg, ..., SKU_10.jpg
        Поддерживает любой регистр в названии файлов
        """
        if not sku:
            return ['/static/img/goods/no-image.jpg']
        
        images = []
        
        # Определяем путь к папке с изображениями
        if current_app:
            goods_path = os.path.join(current_app.static_folder, 'img', 'goods')
        else:
            # Fallback для тестирования без Flask контекста
            goods_path = './app/static/img/goods'
        
        if not os.path.exists(goods_path):
            return ['/static/img/goods/no-image.jpg']
        
        # Получаем список всех файлов в папке
        try:
            all_files = os.listdir(goods_path)
        except OSError:
            return ['/static/img/goods/no-image.jpg']
        
        # Ищем файлы по паттерну SKU_X.jpg (в любом регистре)
        sku_lower = sku.lower()
        for i in range(1, max_images + 1):
            target_filename = f"{sku_lower}_{i}.jpg"
            
            # Ищем файл с учетом регистра
            found_file = None
            for filename in all_files:
                if filename.lower() == target_filename:
                    found_file = filename
                    break
            
            if found_file:
                images.append(f'/static/img/goods/{found_file}')
        
        # Если изображения не найдены, возвращаем заглушку
        if not images:
            return ['/static/img/goods/no-image.jpg']
        
        return images
    
    def get_product_main_image(self, sku: str) -> str:
        """Возвращает основное изображение товара"""
        images = self.find_product_images(sku, max_images=1)
        return images[0] if images else '/static/img/goods/no-image.jpg'
    
    def _load_products(self):
        """Загрузка товаров из CSV в кэш (БЕЗ обработки колонки images)"""
        with self._lock:
            products = {}
            categories = set()
            
            if not os.path.exists(self.csv_path):
                print(f"❌ CSV файл не найден: {self.csv_path}")
                self._cache = products
                self._categories_cache = categories
                return
            
            try:
                with open(self.csv_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    print(f"🔍 DEBUG: Заголовки CSV: {reader.fieldnames}")
                    
                    row_count = 0
                    for row in reader:
                        row_count += 1
                        
                        # Получение и валидация SKU
                        sku = row.get('sku', '').strip()
                        if not sku:
                            print(f"⚠️  DEBUG: Пропущена строка {row_count} - пустой SKU")
                            continue
                        
                        try:
                            # Обработка цен
                            price_str = row.get('price', '0').strip()
                            price = int(price_str) if price_str else 0
                            
                            old_price_str = row.get('old_price', '').strip()
                            old_price = int(old_price_str) if old_price_str else None
                            
                            # Обработка остатков (для совместимости, но не используется в отображении)
                            stock_str = row.get('stock', '0').strip()
                            stock = int(stock_str) if stock_str else 0
                            
                            # Обработка активности
                            is_active_str = row.get('is_active', '1').strip()
                            is_active = is_active_str in ('1', 'true', 'True', 'yes', 'Yes')
                            
                            # ВАЖНО: Убираем обработку колонки images - теперь изображения ищутся автоматически
                            
                            product = {
                                'sku': sku,
                                'title': row.get('title', '').strip(),
                                'price': price,
                                'old_price': old_price,
                                'category': row.get('category', '').strip(),
                                'volume_ml': row.get('volume_ml', '').strip(),
                                'color': row.get('color', '').strip(),
                                'images': self.find_product_images(sku),  # Автопоиск изображений
                                'stock': stock,
                                'is_active': is_active,
                                'description': row.get('description', '').strip()
                            }
                            
                            products[sku] = product
                            print(f"✅ DEBUG: Добавлен товар {sku}: {product['title']} (изображений: {len(product['images'])})")
                            
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
        """Получение товара по SKU"""
        with self._lock:
            product = self._cache.get(sku)
            if product and product['is_active']:
                # Обновляем изображения при каждом запросе (на случай добавления новых файлов)
                product['images'] = self.find_product_images(sku)
                return product
            return None
    
    def search_products(self, query: str = '', category: str = '', 
                       price_min: int = None, price_max: int = None) -> List[Dict]:
        """Поиск товаров с фильтрами"""
        products = self.get_all_products()
        
        if not query and not category and price_min is None and price_max is None:
            return products
        
        result = []
        query_lower = query.lower() if query else ''
        
        for product in products:
            # Фильтр по категории
            if category and product.get('category', '').lower() != category.lower():
                continue
            
            # Фильтр по цене
            if price_min is not None and product['price'] < price_min:
                continue
            if price_max is not None and product['price'] > price_max:
                continue
            
            # Фильтр по поисковому запросу
            if query_lower:
                searchable_text = ' '.join([
                    product.get('title', ''),
                    product.get('description', ''),
                    product.get('sku', ''),
                    product.get('color', ''),
                    product.get('category', '')
                ]).lower()
                
                if query_lower not in searchable_text:
                    continue
            
            result.append(product)
        
        return result
    
    def get_categories(self) -> List[str]:
        """Получение списка всех категорий"""
        with self._lock:
            return sorted(list(self._categories_cache))
    
    def get_featured_products(self, limit: int = 6) -> List[Dict]:
        """Получение рекомендуемых товаров"""
        products = self.get_all_products()
        # Можно добавить логику выбора featured товаров
        return products[:limit]
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.cache = {}
        self.last_modified = 0
        self.lock = threading.RLock()
        self._load_products()
    
    def _load_products(self):
        """Загрузка товаров из CSV в кэш"""
        with self.lock:
            try:
                if not os.path.exists(self.csv_path):
                    self.cache = {}
                    return
                
                current_modified = os.path.getmtime(self.csv_path)
                if current_modified <= self.last_modified and self.cache:
                    return
                
                products = {}
                with open(self.csv_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        sku = row.get('sku', '').strip()
                        if sku:
                            # Преобразование типов
                            try:
                                row['price'] = float(row.get('price', 0))
                            except (ValueError, TypeError):
                                row['price'] = 0.0
                            
                            try:
                                row['old_price'] = float(row.get('old_price', 0)) if row.get('old_price') else None
                            except (ValueError, TypeError):
                                row['old_price'] = None
                            
                            try:
                                row['stock'] = int(row.get('stock', 0))
                            except (ValueError, TypeError):
                                row['stock'] = 0
                            
                            # is_active как boolean
                            row['is_active'] = str(row.get('is_active', '1')).strip() == '1'
                            
                            # Обработка изображений (разделенных | или ,)
                            images_str = row.get('images', '')
                            if images_str:
                                if '|' in images_str:
                                    row['images'] = [img.strip() for img in images_str.split('|') if img.strip()]
                                else:
                                    row['images'] = [img.strip() for img in images_str.split(',') if img.strip()]
                            else:
                                row['images'] = []
                            
                            # Обработка volume_ml
                            try:
                                volume = row.get('volume_ml', '')
                                row['volume_ml'] = int(volume) if volume else None
                            except (ValueError, TypeError):
                                row['volume_ml'] = None
                            
                            products[sku] = row
                
                self.cache = products
                self.last_modified = current_modified
                logging.info(f"Loaded {len(products)} products")
                
            except Exception as e:
                logging.error(f"Error loading products: {e}")
                self.cache = {}
    
    def _save_products(self):
        """Сохранение товаров из кэша в CSV"""
        with self.lock:
            try:
                if not self.cache:
                    return True
                
                # Порядок полей как в вашем CSV
                fieldnames = ['sku', 'title', 'price', 'old_price', 'category', 
                             'volume_ml', 'color', 'images', 'stock', 'is_active', 
                             'date_added', 'description']
                
                # Создаем резервную копию
                if os.path.exists(self.csv_path):
                    backup_path = f"{self.csv_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    os.rename(self.csv_path, backup_path)
                
                # Записываем новый файл
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for sku in sorted(self.cache.keys()):
                        product = self.cache[sku].copy()
                        
                        # Преобразуем списки в строки
                        if 'images' in product and isinstance(product['images'], list):
                            product['images'] = '|'.join(product['images'])
                        
                        # Преобразуем boolean в строку
                        if 'is_active' in product:
                            product['is_active'] = '1' if product['is_active'] else '0'
                        
                        # Обработка пустых значений
                        for field in fieldnames:
                            if field not in product:
                                product[field] = ''
                            elif product[field] is None:
                                product[field] = ''
                        
                        writer.writerow(product)
                
                # Обновляем время модификации
                self.last_modified = os.path.getmtime(self.csv_path)
                logging.info(f"Saved {len(self.cache)} products to CSV")
                return True
                
            except Exception as e:
                logging.error(f"Error saving products: {e}")
                return False
    
    def get_all_products(self, reload=False) -> List[Dict]:
        """Получение всех товаров"""
        if reload:
            self._load_products()
        else:
            # Проверяем, не изменился ли файл
            if os.path.exists(self.csv_path):
                current_modified = os.path.getmtime(self.csv_path)
                if current_modified > self.last_modified:
                    self._load_products()
        
        with self.lock:
            return list(self.cache.values())
    
    def get_product_by_sku(self, sku: str) -> Optional[Dict]:
        """Получение товара по SKU"""
        self.get_all_products()  # Обновляем кэш
        with self.lock:
            return self.cache.get(sku)
    
    def create_product(self, product_data: Dict) -> bool:
        """Создание нового товара"""
        try:
            with self.lock:
                sku = product_data.get('sku', '').strip()
                if not sku:
                    return False
                
                if sku in self.cache:
                    return False  # Товар уже существует
                
                # Подготавливаем данные товара
                new_product = self._prepare_product_data(product_data)
                
                # Добавляем дату создания если её нет
                if not new_product.get('date_added'):
                    new_product['date_added'] = datetime.now().strftime('%Y-%m-%d')
                
                # Добавляем в кэш
                self.cache[sku] = new_product
                
                # Сохраняем в файл
                return self._save_products()
                
        except Exception as e:
            logging.error(f"Error creating product: {e}")
            return False
    
    def update_product(self, sku: str, product_data: Dict) -> bool:
        """Обновление существующего товара"""
        try:
            with self.lock:
                if sku not in self.cache:
                    return False  # Товар не существует
                
                # Сохраняем оригинальные данные
                original_product = self.cache[sku].copy()
                
                # Подготавливаем данные товара
                updated_product = self._prepare_product_data(product_data)
                updated_product['sku'] = sku  # Сохраняем оригинальный SKU
                
                # Сохраняем дату создания если была
                if 'date_added' in original_product and not updated_product.get('date_added'):
                    updated_product['date_added'] = original_product['date_added']
                
                # Обновляем в кэше
                self.cache[sku] = updated_product
                
                # Сохраняем в файл
                return self._save_products()
                
        except Exception as e:
            logging.error(f"Error updating product {sku}: {e}")
            return False
    
    def delete_product(self, sku: str) -> bool:
        """Удаление товара"""
        try:
            with self.lock:
                if sku not in self.cache:
                    return False  # Товар не существует
                
                # Удаляем из кэша
                del self.cache[sku]
                
                # Сохраняем в файл
                return self._save_products()
                
        except Exception as e:
            logging.error(f"Error deleting product {sku}: {e}")
            return False
    
    def _prepare_product_data(self, data: Dict) -> Dict:
        """Подготовка данных товара для сохранения"""
        product = {}
        
        # Обязательные поля
        product['sku'] = data.get('sku', '').strip()
        product['title'] = data.get('title', '').strip()
        product['description'] = data.get('description', '').strip()
        product['category'] = data.get('category', '').strip()
        
        # Числовые поля
        try:
            product['price'] = float(data.get('price', 0))
        except (ValueError, TypeError):
            product['price'] = 0.0
        
        try:
            old_price = data.get('old_price')
            product['old_price'] = float(old_price) if old_price else None
        except (ValueError, TypeError):
            product['old_price'] = None
        
        try:
            product['stock'] = int(data.get('stock', 0))
        except (ValueError, TypeError):
            product['stock'] = 0
        
        try:
            volume = data.get('volume_ml')
            product['volume_ml'] = int(volume) if volume else None
        except (ValueError, TypeError):
            product['volume_ml'] = None
        
        # Дополнительные поля
        product['color'] = data.get('color', '').strip()
        product['date_added'] = data.get('date_added', '').strip()
        
        # Boolean поля
        is_active = data.get('is_active')
        if isinstance(is_active, str):
            product['is_active'] = is_active.lower() in ['1', 'true', 'yes', 'on']
        else:
            product['is_active'] = bool(is_active)
        
        # Обработка изображений
        images = data.get('images', '')
        if isinstance(images, str):
            if '|' in images:
                product['images'] = [img.strip() for img in images.split('|') if img.strip()]
            else:
                product['images'] = [img.strip() for img in images.split(',') if img.strip()]
        elif isinstance(images, list):
            product['images'] = [str(img).strip() for img in images if str(img).strip()]
        else:
            product['images'] = []
        
        return product
    
    def search_products(self, query: str = '', category: str = '', 
                       price_min: float = None, price_max: float = None,
                       only_active: bool = True) -> List[Dict]:
        """Поиск товаров с фильтрами"""
        products = self.get_all_products()
        result = []
        
        query_lower = query.lower() if query else ''
        
        for product in products:
            # Фильтр по активности
            if only_active and not product.get('is_active', True):
                continue
            
            # Фильтр по поисковому запросу
            if query_lower:
                searchable_text = (
                    product.get('title', '') + ' ' +
                    product.get('description', '') + ' ' +
                    product.get('sku', '') + ' ' +
                    product.get('color', '') + ' ' +
                    product.get('category', '')
                ).lower()
                
                if query_lower not in searchable_text:
                    continue
            
            # Фильтр по категории
            if category and product.get('category', '').lower() != category.lower():
                continue
            
            # Фильтр по цене
            price = product.get('price', 0)
            if price_min is not None and price < price_min:
                continue
            if price_max is not None and price > price_max:
                continue
            
            result.append(product)
        
        return result
    
    def get_categories(self) -> List[str]:
        """Получение списка категорий"""
        products = self.get_all_products()
        categories = set()
        for product in products:
            category = product.get('category', '').strip()
            if category:
                categories.add(category)
        return sorted(categories)
    
    def get_products_count(self) -> int:
        """Получение общего количества товаров"""
        return len(self.get_all_products())
    
    def get_active_products_count(self) -> int:
        """Получение количества активных товаров"""
        products = self.get_all_products()
        return sum(1 for p in products if p.get('is_active', True))
    
    def get_featured_products(self, limit: int = 6) -> List[Dict]:
        """Получение рекомендуемых товаров для главной страницы"""
        products = self.get_all_products()
        # Фильтруем только активные товары
        active_products = [p for p in products if p.get('is_active', True)]
        
        # Сортируем по дате добавления (новые сначала)
        active_products.sort(
            key=lambda x: x.get('date_added', ''), 
            reverse=True
        )
        
        return active_products[:limit]
    
    def generate_sku(self, title: str) -> str:
        """Генерация SKU на основе названия"""
        # Берем первые буквы слов
        words = title.upper().split()
        base = ''.join(word[:3] for word in words[:3])
        
        if not base:
            base = "PROD"
        
        # Добавляем числовой суффикс если нужно
        counter = 1
        sku = f"{base}-{counter:03d}"
        while sku in self.cache:
            counter += 1
            sku = f"{base}-{counter:03d}"
        
        return sku
    
    def validate_product_data(self, data: Dict, current_sku: str = None) -> Dict[str, str]:
        """Валидация данных товара"""
        errors = {}
        
        # Проверка SKU
        new_sku = data.get('sku', '').strip()
        if not new_sku:
            errors['sku'] = 'SKU обязателен'
        elif new_sku != current_sku and new_sku in self.cache:
            errors['sku'] = 'Товар с таким SKU уже существует'
        
        # Проверка названия
        if not data.get('title', '').strip():
            errors['title'] = 'Название обязательно'
        
        # Проверка цены
        try:
            price = float(data.get('price', 0))
            if price < 0:
                errors['price'] = 'Цена не может быть отрицательной'
        except (ValueError, TypeError):
            errors['price'] = 'Некорректная цена'
        
        # Проверка старой цены
        old_price = data.get('old_price')
        if old_price:
            try:
                old_price_float = float(old_price)
                if old_price_float < 0:
                    errors['old_price'] = 'Старая цена не может быть отрицательной'
            except (ValueError, TypeError):
                errors['old_price'] = 'Некорректная старая цена'
        
        # Проверка остатка
        try:
            stock = int(data.get('stock', 0))
            if stock < 0:
                errors['stock'] = 'Остаток не может быть отрицательным'
        except (ValueError, TypeError):
            errors['stock'] = 'Некорректный остаток'
        
        # Проверка объема
        volume_ml = data.get('volume_ml')
        if volume_ml:
            try:
                volume = int(volume_ml)
                if volume < 0:
                    errors['volume_ml'] = 'Объем не может быть отрицательным'
            except (ValueError, TypeError):
                errors['volume_ml'] = 'Некорректный объем'
        
        return errors