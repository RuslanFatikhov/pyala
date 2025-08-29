# app/services/encryption.py
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

class DataEncryption:
    """Сервис для шифрования/расшифровки персональных данных"""
    
    def __init__(self):
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)
    
    def _get_encryption_key(self) -> bytes:
        """Получение ключа шифрования из переменной окружения"""
        master_password = os.getenv('DATA_ENCRYPTION_KEY')
        if not master_password:
            raise ValueError("DATA_ENCRYPTION_KEY не установлен в переменных окружения")
        
        # Используем соль для дополнительной безопасности
        salt = os.getenv('ENCRYPTION_SALT', 'default_salt_change_me').encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return key
    
    def encrypt_data(self, data: str) -> str:
        """Шифрование строки данных"""
        try:
            if not data:
                return ""
            encrypted = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logging.error(f"Ошибка шифрования: {e}")
            raise
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Расшифровка строки данных"""
        try:
            if not encrypted_data:
                return ""
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logging.error(f"Ошибка расшифровки: {e}")
            # В случае ошибки расшифровки возвращаем маскированные данные
            return "[ЗАШИФРОВАНО]"
    
    def mask_phone(self, phone: str) -> str:
        """Маскировка телефона для отображения"""
        if len(phone) < 4:
            return "*" * len(phone)
        return phone[:2] + "*" * (len(phone) - 4) + phone[-2:]
    
    def mask_email(self, email: str) -> str:
        """Маскировка email для отображения"""
        if '@' not in email:
            return "*" * len(email)
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked_local}@{domain}"


# app/services/secure_orders.py
import csv
import os
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from .encryption import DataEncryption
import logging

class SecureOrderService:
    """Безопасный сервис для работы с заказами с шифрованием ПД"""
    
    # Поля содержащие персональные данные
    PERSONAL_DATA_FIELDS = ['name', 'phone', 'address', 'comment']
    
    def __init__(self):
        self.csv_path = os.getenv('CSV_ORDERS_PATH', './data/orders.csv')
        self.encryption = DataEncryption()
        self._lock = threading.Lock()
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """Создание CSV файла заказов если не существует"""
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            
            # Устанавливаем безопасные права доступа (только владелец)
            os.umask(0o077)
            
            with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['order_id', 'created_at', 'name_enc', 'phone_enc', 'city', 
                               'address_enc', 'items', 'total', 'comment_enc', 'status'])
            
            # Устанавливаем права только для владельца файла
            os.chmod(self.csv_path, 0o600)
    
    def _encrypt_order_data(self, form_data: Dict) -> Dict:
        """Шифрование персональных данных в заказе"""
        encrypted_data = form_data.copy()
        
        try:
            # Шифруем персональные данные
            encrypted_data['name_enc'] = self.encryption.encrypt_data(form_data.get('name', ''))
            encrypted_data['phone_enc'] = self.encryption.encrypt_data(form_data.get('phone', ''))
            encrypted_data['address_enc'] = self.encryption.encrypt_data(form_data.get('address', ''))
            encrypted_data['comment_enc'] = self.encryption.encrypt_data(form_data.get('comment', ''))
            
            # city оставляем незашифрованным для аналитики
            
        except Exception as e:
            logging.error(f"Ошибка шифрования данных заказа: {e}")
            raise
        
        return encrypted_data
    
    def _decrypt_order_data(self, encrypted_data: Dict) -> Dict:
        """Расшифровка персональных данных заказа"""
        decrypted_data = encrypted_data.copy()
        
        try:
            decrypted_data['name'] = self.encryption.decrypt_data(encrypted_data.get('name_enc', ''))
            decrypted_data['phone'] = self.encryption.decrypt_data(encrypted_data.get('phone_enc', ''))
            decrypted_data['address'] = self.encryption.decrypt_data(encrypted_data.get('address_enc', ''))
            decrypted_data['comment'] = self.encryption.decrypt_data(encrypted_data.get('comment_enc', ''))
            
        except Exception as e:
            logging.error(f"Ошибка расшифровки данных заказа: {e}")
            # Возвращаем маскированные данные при ошибке
            decrypted_data['name'] = "[ОШИБКА РАСШИФРОВКИ]"
            decrypted_data['phone'] = "[ОШИБКА РАСШИФРОВКИ]"
            decrypted_data['address'] = "[ОШИБКА РАСШИФРОВКИ]"
            decrypted_data['comment'] = "[ОШИБКА РАСШИФРОВКИ]"
        
        return decrypted_data
    
    def create_order(self, form_data: Dict, cart_items: List[Dict]) -> Optional[int]:
        """Создание заказа с шифрованием ПД"""
        with self._lock:
            try:
                order_id = self._get_next_order_id()
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
                
                # Шифрование персональных данных
                encrypted_data = self._encrypt_order_data(form_data)
                
                items_str = '|'.join([f"{item['product']['sku']}:{item['qty']}" 
                                    for item in cart_items])
                total = sum(item['total'] for item in cart_items)
                
                # Запись в CSV с зашифрованными данными
                with open(self.csv_path, 'a', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        order_id,
                        created_at,
                        encrypted_data['name_enc'],
                        encrypted_data['phone_enc'],
                        form_data['city'],  # Город не шифруем
                        encrypted_data['address_enc'],
                        items_str,
                        total,
                        encrypted_data['comment_enc'],
                        'new'
                    ])
                
                logging.info(f"Заказ {order_id} создан с шифрованием ПД")
                return order_id
                
            except Exception as e:
                logging.error(f"Ошибка создания заказа: {e}")
                return None
    
    def get_order_for_admin(self, order_id: int, decrypt: bool = False) -> Optional[Dict]:
        """Получение заказа для админа (с возможностью расшифровки)"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('order_id', 0)) == order_id:
                        if decrypt:
                            # Полная расшифровка для админа
                            return self._decrypt_order_data(row)
                        else:
                            # Маскированные данные для обычного просмотра
                            return self._mask_order_data(row)
        except Exception as e:
            logging.error(f"Ошибка получения заказа {order_id}: {e}")
        return None
    
    def _mask_order_data(self, order_data: Dict) -> Dict:
        """Маскировка ПД для безопасного отображения"""
        masked = order_data.copy()
        
        try:
            # Расшифровываем только для маскировки
            name = self.encryption.decrypt_data(order_data.get('name_enc', ''))
            phone = self.encryption.decrypt_data(order_data.get('phone_enc', ''))
            
            # Маскируем данные
            masked['name_masked'] = name[:2] + "*" * max(0, len(name) - 2) if name else ""
            masked['phone_masked'] = self.encryption.mask_phone(phone) if phone else ""
            
        except Exception:
            masked['name_masked'] = "[ЗАШИФРОВАНО]"
            masked['phone_masked'] = "[ЗАШИФРОВАНО]"
        
        return masked
    
    def cleanup_old_orders(self, days: int = 365) -> int:
        """Удаление старых заказов (соблюдение требований GDPR)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        try:
            orders_to_keep = []
            deleted_count = 0
            
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                for row in reader:
                    try:
                        order_date = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M')
                        if order_date >= cutoff_date:
                            orders_to_keep.append(row)
                        else:
                            deleted_count += 1
                    except ValueError:
                        # Оставляем заказы с некорректной датой
                        orders_to_keep.append(row)
            
            # Перезаписываем файл без старых заказов
            temp_path = self.csv_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(orders_to_keep)
            
            os.replace(temp_path, self.csv_path)
            os.chmod(self.csv_path, 0o600)
            
            logging.info(f"Удалено {deleted_count} старых заказов")
            return deleted_count
            
        except Exception as e:
            logging.error(f"Ошибка очистки старых заказов: {e}")
            return 0
    
    def _get_next_order_id(self) -> int:
        """Получение следующего ID заказа"""
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


