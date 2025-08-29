#!/usr/bin/env python3
"""
Детальный тест веб-интерфейса с диагностикой
"""
import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "http://localhost:5001"
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')

def detailed_product_test():
    print("🔍 ДЕТАЛЬНЫЙ ТЕСТ СОЗДАНИЯ/РЕДАКТИРОВАНИЯ ТОВАРОВ")
    print("=" * 60)
    
    session = requests.Session()
    
    # Вход в систему
    login_url = f"{BASE_URL}/admin/login"
    session.get(login_url)
    login_data = {'username': ADMIN_USERNAME, 'password': ADMIN_PASSWORD}
    session.post(login_url, data=login_data)
    
    # Уникальный SKU для теста
    test_sku = f"DETAILED-{int(time.time())}"
    print(f"🏷️ Тестовый SKU: {test_sku}")
    
    # 1. Создание товара
    print(f"\n1️⃣ Создание товара {test_sku}")
    create_url = f"{BASE_URL}/admin/products/create"
    
    test_product = {
        'sku': test_sku,
        'title': 'Детальный тест товар',
        'description': 'Создано для детального тестирования',
        'category': 'пиалы',
        'price': '5990',
        'stock': '10',
        'color': 'белый',
        'volume_ml': '90',
        'is_active': 'on'
    }
    
    response = session.post(create_url, data=test_product, allow_redirects=False)
    print(f"   Статус создания: {response.status_code}")
    
    if response.status_code in [302, 303]:
        print("   ✅ Редирект получен (товар создан)")
        
        # Проверяем немедленно в списке
        time.sleep(0.5)  # Небольшая задержка
        response = session.get(f"{BASE_URL}/admin/products")
        if test_sku in response.text:
            print("   ✅ Товар найден в списке")
        else:
            print("   ❌ Товар НЕ найден в списке")
            # Показываем часть ответа для диагностики
            print(f"   Длина ответа: {len(response.text)} символов")
    else:
        print(f"   ❌ Ошибка создания: {response.status_code}")
        print(f"   Ответ: {response.text[:500]}")
        return
    
    # 2. Редактирование товара
    print(f"\n2️⃣ Редактирование товара {test_sku}")
    edit_url = f"{BASE_URL}/admin/products/{test_sku}/edit"
    
    response = session.get(edit_url)
    print(f"   Доступ к странице редактирования: {response.status_code}")
    
    if response.status_code == 200:
        # Проверяем, что форма содержит данные товара
        if test_sku in response.text and 'Детальный тест товар' in response.text:
            print("   ✅ Форма заполнена данными товара")
        else:
            print("   ❌ Форма не содержит данные товара")
        
        # Обновляем товар
        updated_data = test_product.copy()
        updated_data['title'] = 'Обновленный детальный тест'
        updated_data['price'] = '6990'
        
        response = session.post(edit_url, data=updated_data, allow_redirects=False)
        print(f"   Статус обновления: {response.status_code}")
        
        if response.status_code in [302, 303]:
            print("   ✅ Товар обновлен")
        else:
            print(f"   ❌ Ошибка обновления: {response.text[:300]}")
    
    # 3. Удаление товара
    print(f"\n3️⃣ Удаление товара {test_sku}")
    delete_url = f"{BASE_URL}/admin/products/{test_sku}/delete"
    
    headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    response = session.post(delete_url, headers=headers)
    print(f"   Статус удаления: {response.status_code}")
    
    if response.status_code == 200:
        try:
            result = response.json()
            if result.get('ok'):
                print("   ✅ Товар удален")
            else:
                print(f"   ❌ Ошибка удаления: {result.get('error')}")
        except:
            print(f"   ❌ Некорректный ответ: {response.text}")
    else:
        print(f"   ❌ HTTP ошибка удаления: {response.status_code}")
    
    print(f"\n✅ Детальный тест завершен")

if __name__ == "__main__":
    detailed_product_test()
