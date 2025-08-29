#!/usr/bin/env python3
import csv
import os
import shutil
from datetime import datetime
import sys

# Добавляем путь к проекту
sys.path.append('.')

def migrate_orders():
    print("🔐 МИГРАЦИЯ ДАННЫХ ЗАКАЗОВ К ЗАШИФРОВАННОМУ ФОРМАТУ")
    print("=" * 55)
    
    try:
        from app.services.encryption import DataEncryption
        
        orders_file = 'data/orders.csv'
        
        if not os.path.exists(orders_file):
            print("❌ Файл заказов не найден")
            return
        
        # Проверяем, не зашифрованы ли уже данные
        with open(orders_file, 'r', encoding='utf-8') as f:
            header = f.readline().strip()
            if 'name_enc' in header:
                print("ℹ️  Данные уже зашифрованы")
                return
        
        print("🔍 Анализируем существующие данные...")
        
        # Читаем текущие данные
        with open(orders_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            orders = list(reader)
        
        print(f"📋 Найдено заказов для миграции: {len(orders)}")
        
        if len(orders) == 0:
            print("ℹ️  Нет данных для миграции")
            return
        
        # Создаем бэкап
        backup_file = f"data/orders_before_encryption_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        shutil.copy2(orders_file, backup_file)
        print(f"💾 Создан бэкап: {backup_file}")
        
        # Инициализируем шифрование
        encryption = DataEncryption()
        
        # Создаем новый зашифрованный файл
        temp_file = orders_file + '.encrypted.tmp'
        
        with open(temp_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Записываем новый заголовок с зашифрованными полями
            writer.writerow(['order_id', 'created_at', 'name_enc', 'phone_enc', 
                           'city', 'address_enc', 'items', 'total', 'comment_enc', 'status'])
            
            # Шифруем и записываем данные
            for i, order in enumerate(orders, 1):
                try:
                    encrypted_row = [
                        order.get('order_id', ''),
                        order.get('created_at', ''),
                        encryption.encrypt_data(order.get('name', '')),
                        encryption.encrypt_data(order.get('phone', '')),
                        order.get('city', ''),  # Город не шифруем
                        encryption.encrypt_data(order.get('address', '')),
                        order.get('items', ''),
                        order.get('total', ''),
                        encryption.encrypt_data(order.get('comment', '')),
                        order.get('status', 'new')
                    ]
                    writer.writerow(encrypted_row)
                    print(f"🔐 Зашифрован заказ {i}/{len(orders)}: #{order.get('order_id', 'N/A')}")
                    
                except Exception as e:
                    print(f"❌ Ошибка шифрования заказа #{order.get('order_id', 'N/A')}: {e}")
                    return
        
        # Заменяем оригинальный файл
        shutil.move(temp_file, orders_file)
        
        # Устанавливаем безопасные права
        os.chmod(orders_file, 0o600)
        
        print(f"\n✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print(f"🔐 Зашифровано заказов: {len(orders)}")
        print(f"💾 Резервная копия: {backup_file}")
        print(f"🔒 Установлены безопасные права доступа")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта модулей: {e}")
        print("   Убедитесь что модули шифрования созданы")
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")

if __name__ == "__main__":
    migrate_orders()
