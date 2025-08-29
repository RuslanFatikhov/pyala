#!/usr/bin/env python3
"""
Скрипт для тестирования админки через командную строку
"""
import os
import sys
import requests
import json
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

BASE_URL = "http://localhost:5000"
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')

def test_admin_auth():
    """Тест аутентификации в админке"""
    print("🔐 Тестирование аутентификации...")
    
    session = requests.Session()
    
    # Получаем страницу входа
    login_url = f"{BASE_URL}/admin/login"
    try:
        response = session.get(login_url, timeout=5)
        print(f"   Страница входа: {response.status_code}")
        
        if response.status_code != 200:
            print("   ❌ Страница входа недоступна")
            return False, None
        
        # Пытаемся войти
        login_data = {
            'username': ADMIN_USERNAME,
            'password': ADMIN_PASSWORD
        }
        
        response = session.post(login_url, data=login_data, allow_redirects=False, timeout=5)
        
        if response.status_code in [302, 303]:
            print("   ✅ Аутентификация успешна")
            return True, session
        else:
            print(f"   ❌ Ошибка аутентификации: {response.status_code}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False, None

def test_products_list(session):
    """Тест списка товаров"""
    print("\n📋 Тестирование списка товаров...")
    
    try:
        response = session.get(f"{BASE_URL}/admin/products", timeout=5)
        print(f"   Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            if 'Товары' in content:
                print("   ✅ Страница товаров загружена")
                
                # Проверяем наличие ключевых элементов
                has_create_button = 'Создать товар' in content or 'products/create' in content
                has_table = '<table' in content or 'Товары не найдены' in content
                
                print(f"   Кнопка создания: {'✅' if has_create_button else '❌'}")
                print(f"   Таблица/сообщение: {'✅' if has_table else '❌'}")
                
                return True
            else:
                print("   ❌ Неправильное содержимое страницы")
                return False
        else:
            print(f"   ❌ Ошибка загрузки: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False

def test_product_creation(session):
    """Тест создания товара"""
    print("\n➕ Тестирование создания товара...")
    
    # Тестовые данные
    test_product = {
        'sku': 'CLI-TEST-001',
        'title': 'CLI Тестовая пиала',
        'description': 'Создано через командную строку',
        'category': 'пиалы',
        'price': '5990',
        'stock': '10',
        'is_active': 'on'
    }
    
    try:
        # Получаем страницу создания
        create_url = f"{BASE_URL}/admin/products/create"
        response = session.get(create_url, timeout=5)
        
        if response.status_code != 200:
            print(f"   ❌ Страница создания недоступна: {response.status_code}")
            return False, None
        
        print("   ✅ Страница создания доступна")
        
        # Отправляем данные
        response = session.post(create_url, data=test_product, allow_redirects=False, timeout=5)
        
        if response.status_code in [302, 303]:
            print("   ✅ Товар создан (получен редирект)")
            return True, test_product['sku']
        elif response.status_code == 200:
            # Возможно есть ошибки валидации
            if 'error-message' in response.text or 'уже существует' in response.text:
                print("   ⚠️ Ошибка валидации (возможно, товар уже существует)")
                return False, None
            else:
                print("   ❌ Неожиданный ответ при создании")
                return False, None
        else:
            print(f"   ❌ Ошибка создания товара: {response.status_code}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False, None

def test_product_editing(session, sku):
    """Тест редактирования товара"""
    print(f"\n✏️ Тестирование редактирования товара {sku}...")
    
    try:
        edit_url = f"{BASE_URL}/admin/products/{sku}/edit"
        response = session.get(edit_url, timeout=5)
        
        if response.status_code != 200:
            print(f"   ❌ Страница редактирования недоступна: {response.status_code}")
            return False
        
        print("   ✅ Страница редактирования доступна")
        
        # Обновляем товар
        updated_data = {
            'sku': sku,
            'title': f'CLI Обновлённая пиала {sku}',
            'description': 'Обновлено через командную строку',
            'category': 'пиалы',
            'price': '6990',  # Изменили цену
            'stock': '5',     # Изменили остаток
            'is_active': 'on'
        }
        
        response = session.post(edit_url, data=updated_data, allow_redirects=False, timeout=5)
        
        if response.status_code in [302, 303]:
            print("   ✅ Товар обновлён успешно")
            return True
        else:
            print(f"   ❌ Ошибка обновления: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False

def test_product_deletion(session, sku):
    """Тест удаления товара"""
    print(f"\n🗑️ Тестирование удаления товара {sku}...")
    
    try:
        delete_url = f"{BASE_URL}/admin/products/{sku}/delete"
        
        # Отправляем AJAX-запрос
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        response = session.post(delete_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('ok'):
                    print("   ✅ Товар удалён успешно")
                    return True
                else:
                    print(f"   ❌ Ошибка удаления: {result.get('error', 'Неизвестная ошибка')}")
                    return False
            except json.JSONDecodeError:
                print("   ❌ Некорректный JSON ответ")
                return False
        else:
            print(f"   ❌ Ошибка удаления: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False

def main():
    print("🚀 ТЕСТИРОВАНИЕ АДМИНКИ ТОВАРОВ")
    print("=" * 50)
    
    # Проверяем, запущено ли приложение
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Приложение запущено и отвечает")
        else:
            print("⚠️ Приложение запущено, но есть проблемы")
    except requests.exceptions.RequestException:
        print("❌ Приложение не запущено или недоступно")
        print("   Запустите: python run.py")
        return
    
    # Тестируем аутентификацию
    auth_success, session = test_admin_auth()
    if not auth_success:
        print("\n❌ Тестирование прервано из-за ошибки аутентификации")
        return
    
    # Тестируем список товаров
    list_success = test_products_list(session)
    
    # Тестируем создание товара
    create_success, created_sku = test_product_creation(session)
    
    if create_success and created_sku:
        # Тестируем редактирование
        edit_success = test_product_editing(session, created_sku)
        
        # Тестируем удаление
        delete_success = test_product_deletion(session, created_sku)
    else:
        edit_success = False
        delete_success = False
    
    # Итоговый отчёт
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ ОТЧЁТ:")
    print("=" * 50)
    
    results = {
        'Аутентификация': auth_success,
        'Список товаров': list_success,
        'Создание товара': create_success,
        'Редактирование': edit_success,
        'Удаление товара': delete_success,
    }
    
    for test_name, passed in results.items():
        status = "✅ ПРОЙДЕН" if passed else "❌ ПРОВАЛЕН"
        print(f"{test_name:<20} {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    print("-" * 50)
    print(f"ВСЕГО ТЕСТОВ: {total_tests}")
    print(f"ПРОЙДЕНО: {passed_tests}")
    print(f"ПРОВАЛЕНО: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 Все тесты пройдены!")
        return 0
    else:
        print(f"\n⚠️ {total_tests - passed_tests} тестов провалены")
        return 1

if __name__ == "__main__":
    exit(main())
