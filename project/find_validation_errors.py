#!/usr/bin/env python3
import requests
import re
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "http://localhost:5001"
session = requests.Session()

# Логин
login_url = f"{BASE_URL}/admin/login"
session.get(login_url)
session.post(login_url, data={'username': os.getenv('ADMIN_USERNAME', 'admin'), 'password': os.getenv('ADMIN_PASSWORD', 'admin')})

# Тест с полными данными
test_data = {
    'sku': 'FULL-TEST-001',
    'title': 'Полный тест товар',
    'description': 'Полное описание товара',
    'category': 'пиалы',
    'price': '5990',
    'old_price': '',
    'stock': '10',
    'volume_ml': '90',
    'color': 'белый',
    'is_active': 'on',
    'images': ''
}

print("Тестируем создание с полными данными:")
response = session.post(f"{BASE_URL}/admin/products/create", data=test_data)
print(f"Статус: {response.status_code}")

# Ищем все ошибки в HTML
errors = re.findall(r'<div[^>]*error-message[^>]*>([^<]+)</div>', response.text, re.IGNORECASE)
if errors:
    print("Найденные ошибки:")
    for error in errors:
        print(f"  - {error.strip()}")
else:
    print("Ошибки валидации не найдены")

# Ищем flash сообщения
flash_messages = re.findall(r'<div[^>]*alert[^>]*>([^<]+)</div>', response.text, re.IGNORECASE)
if flash_messages:
    print("Flash сообщения:")
    for msg in flash_messages:
        print(f"  - {msg.strip()}")

# Проверяем, есть ли товар в файле
with open('data/products.csv', 'r') as f:
    if 'FULL-TEST-001' in f.read():
        print("✅ Товар сохранен в CSV")
    else:
        print("❌ Товар НЕ сохранен в CSV")

# Показываем кусок HTML для диагностики
print(f"\nДлина HTML ответа: {len(response.text)}")
print("Первые 500 символов ответа:")
print(response.text[:500])
