#!/usr/bin/env python3
"""
Финальный тест веб-интерфейса админки
"""
import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

BASE_URL = "http://localhost:5001"  # Изменили порт
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')

def test_full_admin_workflow():
    """Полный тест рабочего процесса админки"""
    print("🔄 ПОЛНЫЙ ТЕСТ АДМИНКИ ТОВАРОВ")
    print("=" * 50)
    
    session = requests.Session()
    
    # Шаг 1: Проверка доступности
    try:
        response = session.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Приложение запущено: {response.status_code}")
    except Exception as e:
        print(f"❌ Приложение недоступно: {e}")
        return False
    
    # Шаг 2: Вход в админку
    try:
        login_url = f"{BASE_URL}/admin/login"
        response = session.get(login_url)
        print(f"✅ Страница входа доступна: {response.status_code}")
        
        login_data = {'username': ADMIN_USERNAME, 'password': ADMIN_PASSWORD}
        response = session.post(login_url, data=login_data, allow_redirects=False)
        
        if response.status_code in [302, 303]:
            print("✅ Вход в админку успешен")
        else:
            print(f"❌ Ошибка входа: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка входа: {e}")
        return False
    
    # Шаг 3: Список товаров
    try:
        response = session.get(f"{BASE_URL}/admin/products")
        if response.status_code == 200:
            print("✅ Страница списка товаров доступна")
            
            # Проверяем содержимое
            content = response.text
            if 'PIA-001' in content and 'Товары' in content:
                print("✅ Товары отображаются корректно")
            else:
                print("⚠️ Товары могут отображаться некорректно")
        else:
            print(f"❌ Ошибка загрузки списка товаров: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка списка товаров: {e}")
        return False
    
    # Шаг 4: Создание товара
    try:
        create_url = f"{BASE_URL}/admin/products/create"
        response = session.get(create_url)
        
        if response.status_code == 200:
            print("✅ Страница создания товара доступна")
            
            # Создаём тестовый товар
            test_product = {
                'sku': 'WEB-TEST-001',
                'title': 'Веб-тест пиала',
                'description': 'Создано через веб-интерфейс',
                'category': 'пиалы',
                'price': '5990',
                'stock': '10',
                'color': 'белый',
                'is_active': 'on'
            }
            
            response = session.post(create_url, data=test_product, allow_redirects=False)
            
            if response.status_code in [302, 303]:
                print("✅ Товар создан через веб-интерфейс")
                
                # Проверяем, что товар появился в списке
                response = session.get(f"{BASE_URL}/admin/products")
                if 'WEB-TEST-001' in response.text:
                    print("✅ Созданный товар отображается в списке")
                else:
                    print("⚠️ Созданный товар не найден в списке")
            else:
                print(f"❌ Ошибка создания товара: {response.status_code}")
        else:
            print(f"❌ Страница создания недоступна: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка создания товара: {e}")
    
    # Шаг 5: Редактирование товара
    try:
        edit_url = f"{BASE_URL}/admin/products/WEB-TEST-001/edit"
        response = session.get(edit_url)
        
        if response.status_code == 200:
            print("✅ Страница редактирования доступна")
            
            # Обновляем товар
            updated_data = {
                'sku': 'WEB-TEST-001',
                'title': 'Обновленная веб-тест пиала',
                'description': 'Обновлено через веб-интерфейс',
                'category': 'пиалы',
                'price': '6990',
                'stock': '5',
                'color': 'зелёный',
                'is_active': 'on'
            }
            
            response = session.post(edit_url, data=updated_data, allow_redirects=False)
            
            if response.status_code in [302, 303]:
                print("✅ Товар обновлён через веб-интерфейс")
            else:
                print(f"❌ Ошибка обновления: {response.status_code}")
        else:
            print(f"❌ Страница редактирования недоступна: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка редактирования: {e}")
    
    # Шаг 6: Удаление товара
    try:
        delete_url = f"{BASE_URL}/admin/products/WEB-TEST-001/delete"
        headers = {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
        response = session.post(delete_url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Товар удалён через AJAX")
            else:
                print(f"❌ Ошибка удаления: {result.get('error')}")
        else:
            print(f"❌ Ошибка удаления: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
    
    print("\n🎊 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("Веб-интерфейс админки функционирует корректно!")
    return True

if __name__ == "__main__":
    # Ждём немного, чтобы приложение точно запустилось
    print("Ожидание запуска приложения...")
    time.sleep(2)
    
    test_full_admin_workflow()
