import re
from typing import Dict, List, Tuple
import csv
from io import StringIO

class CheckoutValidator:
    """Валидатор формы оформления заказа"""
    
    def __init__(self):
        self.phone_pattern = re.compile(r'^\+?[0-9\s\-\(\)]{10,15}$')
    
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
