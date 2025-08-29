import re
from typing import Dict, List, Tuple
import csv
from io import StringIO

class CheckoutValidator:
    """Валидатор формы оформления заказа"""
    
    def __init__(self):
        self.phone_pattern = re.compile(r'^\+?[0-9\s\-\(\)]+$')
    
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
    
    # Убираем колонку 'images' из обязательных - теперь изображения автоматические
    REQUIRED_COLUMNS = [
        'sku', 'title', 'price', 'old_price', 'category', 
        'volume_ml', 'color', 'stock', 'is_active', 'description'
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
            
            # Проверка обязательных колонок
            missing_columns = set(self.REQUIRED_COLUMNS) - set(reader.fieldnames)
            if missing_columns:
                errors.append(f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}")
            
            # Предупреждение о колонке images
            if 'images' in reader.fieldnames:
                errors.append("⚠️ ВНИМАНИЕ: Колонка 'images' игнорируется. Изображения загружаются автоматически по SKU из папки static/img/goods/")
            
            # Проверка данных
            skus = set()
            line_num = 1
            
            for row in reader:
                line_num += 1
                line_prefix = f"Строка {line_num}"
                
                # SKU
                sku = row.get('sku', '').strip()
                if not sku:
                    errors.append(f"{line_prefix}: SKU не может быть пустым")
                elif sku in skus:
                    errors.append(f"{line_prefix}: Дублирующийся SKU '{sku}'")
                else:
                    skus.add(sku)
                
                # Название
                title = row.get('title', '').strip()
                if not title:
                    errors.append(f"{line_prefix}: Название товара не может быть пустым")
                
                # Цена
                price_str = row.get('price', '').strip()
                if not price_str:
                    errors.append(f"{line_prefix}: Цена обязательна")
                else:
                    try:
                        price = float(price_str)
                        if price < 0:
                            errors.append(f"{line_prefix}: Цена не может быть отрицательной")
                    except ValueError:
                        errors.append(f"{line_prefix}: Некорректная цена '{price_str}'")
                
                # Старая цена (опционально)
                old_price_str = row.get('old_price', '').strip()
                if old_price_str:
                    try:
                        old_price = float(old_price_str)
                        if old_price < 0:
                            errors.append(f"{line_prefix}: Старая цена не может быть отрицательной")
                    except ValueError:
                        errors.append(f"{line_prefix}: Некорректная старая цена '{old_price_str}'")
                
                # Остаток
                stock_str = row.get('stock', '').strip()
                if stock_str:
                    try:
                        stock = int(stock_str)
                        if stock < 0:
                            errors.append(f"{line_prefix}: Остаток не может быть отрицательным")
                    except ValueError:
                        errors.append(f"{line_prefix}: Некорректный остаток '{stock_str}'")
                
                # Активность товара
                is_active_str = row.get('is_active', '').strip()
                if is_active_str not in ('0', '1', '', 'true', 'false', 'True', 'False'):
                    errors.append(f"{line_prefix}: is_active должно быть 0, 1, true или false")
            
            # Проверка минимального количества товаров
            if len(skus) == 0:
                errors.append("CSV файл не содержит валидных товаров")
        
        except Exception as e:
            errors.append(f"Ошибка парсинга CSV: {str(e)}")
        
        is_valid = len(errors) == 0
        return is_valid, errors