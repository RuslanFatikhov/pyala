import csv
import os
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from .encryption import DataEncryption
import logging

try:
    import portalocker
except ImportError:
    portalocker = None

class SecureOrderService:
    def __init__(self):
        self.csv_path = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        self.encryption = DataEncryption()
        self._lock = threading.Lock()
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['order_id', 'created_at', 'name_enc', 'phone_enc', 'city', 
                               'address_enc', 'items', 'total', 'comment_enc', 'status'])
            os.chmod(self.csv_path, 0o600)
    
    def _encrypt_order_data(self, form_data: Dict) -> Dict:
        encrypted_data = form_data.copy()
        try:
            encrypted_data['name_enc'] = self.encryption.encrypt_data(form_data.get('name', ''))
            encrypted_data['phone_enc'] = self.encryption.encrypt_data(form_data.get('phone', ''))
            encrypted_data['address_enc'] = self.encryption.encrypt_data(form_data.get('address', ''))
            encrypted_data['comment_enc'] = self.encryption.encrypt_data(form_data.get('comment', ''))
        except Exception as e:
            logging.error(f"Ошибка шифрования данных заказа: {e}")
            raise
        return encrypted_data
    
    def _decrypt_order_data(self, encrypted_data: Dict) -> Dict:
        decrypted_data = encrypted_data.copy()
        try:
            decrypted_data['name'] = self.encryption.decrypt_data(encrypted_data.get('name_enc', ''))
            decrypted_data['phone'] = self.encryption.decrypt_data(encrypted_data.get('phone_enc', ''))
            decrypted_data['address'] = self.encryption.decrypt_data(encrypted_data.get('address_enc', ''))
            decrypted_data['comment'] = self.encryption.decrypt_data(encrypted_data.get('comment_enc', ''))
        except Exception as e:
            logging.error(f"Ошибка расшифровки данных заказа: {e}")
            decrypted_data['name'] = "[ОШИБКА РАСШИФРОВКИ]"
            decrypted_data['phone'] = "[ОШИБКА РАСШИФРОВКИ]"
            decrypted_data['address'] = "[ОШИБКА РАСШИФРОВКИ]"
            decrypted_data['comment'] = "[ОШИБКА РАСШИФРОВКИ]"
        return decrypted_data
    
    def create_order(self, form_data: Dict, cart_items: List[Dict]) -> Optional[int]:
        with self._lock:
            try:
                order_id = self._get_next_order_id()
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
                encrypted_data = self._encrypt_order_data(form_data)
                items_str = '|'.join([f"{item['product']['sku']}:{item['qty']}" for item in cart_items])
                total = sum(item['total'] for item in cart_items)
                
                with open(self.csv_path, 'a', encoding='utf-8', newline='') as f:
                    if portalocker:
                        portalocker.lock(f, portalocker.LOCK_EX)
                    try:
                        writer = csv.writer(f)
                        writer.writerow([order_id, created_at, encrypted_data['name_enc'],
                                       encrypted_data['phone_enc'], form_data['city'],
                                       encrypted_data['address_enc'], items_str, total,
                                       encrypted_data['comment_enc'], 'new'])
                    finally:
                        if portalocker:
                            portalocker.unlock(f)
                
                return order_id
            except Exception as e:
                logging.error(f"Ошибка создания заказа: {e}")
                return None
    
    def get_order_for_admin(self, order_id: int, decrypt: bool = False) -> Optional[Dict]:
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('order_id', 0)) == order_id:
                        if decrypt:
                            return self._decrypt_order_data(row)
                        else:
                            return self._mask_order_data(row)
        except Exception as e:
            logging.error(f"Ошибка получения заказа {order_id}: {e}")
        return None
    
    def _mask_order_data(self, order_data: Dict) -> Dict:
        masked = order_data.copy()
        try:
            name = self.encryption.decrypt_data(order_data.get('name_enc', ''))
            phone = self.encryption.decrypt_data(order_data.get('phone_enc', ''))
            masked['name_masked'] = name[:2] + "*" * max(0, len(name) - 2) if name else ""
            masked['phone_masked'] = self.encryption.mask_phone(phone) if phone else ""
        except Exception:
            masked['name_masked'] = "[ЗАШИФРОВАНО]"
            masked['phone_masked'] = "[ЗАШИФРОВАНО]"
        return masked
    
    def get_orders_paginated(self, status_filter: str = '', page: int = 1, 
                           per_page: int = 20) -> Tuple[List[Dict], int]:
        try:
            orders = []
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if status_filter and row.get('status') != status_filter:
                        continue
                    orders.append(self._mask_order_data(row))
            
            orders.sort(key=lambda x: int(x.get('order_id', 0)), reverse=True)
            total = len(orders)
            total_pages = (total + per_page - 1) // per_page
            start = (page - 1) * per_page
            end = start + per_page
            orders = orders[start:end]
            return orders, total_pages
        except Exception as e:
            logging.error(f"Ошибка получения заказов: {e}")
            return [], 0
    
    def get_orders_count(self) -> int:
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return max(0, len(lines) - 1)
        except:
            return 0
    
    def get_new_orders_count(self) -> int:
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
        with self._lock:
            try:
                orders = []
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        if int(row.get('order_id', 0)) == order_id:
                            row['status'] = new_status
                        orders.append(row)
                
                temp_path = self.csv_path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8', newline='') as f:
                    if portalocker:
                        portalocker.lock(f, portalocker.LOCK_EX)
                    try:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(orders)
                    finally:
                        if portalocker:
                            portalocker.unlock(f)
                
                os.replace(temp_path, self.csv_path)
                os.chmod(self.csv_path, 0o600)
                return True
            except Exception as e:
                logging.error(f"Ошибка обновления статуса заказа: {e}")
                return False
    
    def _get_next_order_id(self) -> int:
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) <= 1:
                    return 100001
                max_id = 100000
                for line in lines[1:]:
                    try:
                        order_id = int(line.split(',')[0])
                        max_id = max(max_id, order_id)
                    except (ValueError, IndexError):
                        continue
                return max_id + 1
        except:
            return 100001
