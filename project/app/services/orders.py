### app/services/orders.py
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