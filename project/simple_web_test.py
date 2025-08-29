#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5001"
session = requests.Session()

# Логин
login_url = f"{BASE_URL}/admin/login"
session.get(login_url)
session.post(login_url, data={'username': os.getenv('ADMIN_USERNAME', 'admin'), 'password': os.getenv('ADMIN_PASSWORD', 'admin')})

# Попытка создания с минимальными данными
test_data = {
    'sku': 'SIMPLE-TEST',
    'title': 'Простой тест',
    'price': '1000',
    'category': 'тест'
}

response = session.post(f"{BASE_URL}/admin/products/create", data=test_data)
print(f"Создание товара: {response.status_code}")
print(f"Длина ответа: {len(response.text)}")

# Проверяем на наличие ошибок в HTML
if 'error' in response.text.lower():
    print("Обнаружены ошибки в ответе")
    # Ищем сообщения об ошибках
    import re
    errors = re.findall(r'error-message[^>]*>([^<]+)', response.text, re.IGNORECASE)
    for error in errors:
        print(f"  Ошибка: {error}")

# Проверяем файл
with open('data/products.csv', 'r') as f:
    content = f.read()
    if 'SIMPLE-TEST' in content:
        print("✅ Товар найден в CSV")
    else:
        print("❌ Товар НЕ найден в CSV")
