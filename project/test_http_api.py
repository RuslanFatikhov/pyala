#!/usr/bin/env python3
"""
Тест HTTP API админки
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5000"
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')

def test_app_running():
    """Проверка, что приложение запущено"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"🌐 Приложение отвечает: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Приложение недоступно: {e}")
        return False

def test_admin_login():
    """Тест входа в админку"""
    if not test_app_running():
        return False, None
    
    session = requests.Session()
    
    try:
        # Получаем страницу входа
        login_url = f"{BASE_URL}/admin/login"
        response = session.get(login_url, timeout=5)
        print(f"🔐 Страница входа: {response.status_code}")
        
        if response.status_code != 200:
            return False, None
        
        # Логинимся
        login_data = {
            'username': ADMIN_USERNAME,
            'password': ADMIN_PASSWORD
        }
        
        response = session.post(login_url, data=login_data, allow_redirects=False, timeout=5)
        print(f"🔑 Попытка входа: {response.status_code}")
        
        if response.status_code in [302, 303]:
            print("✅ Вход в админку успешен")
            return True, session
        else:
            print("❌ Ошибка входа")
            return False, None
            
    except Exception as e:
        print(f"❌ Ошибка при входе: {e}")
        return False, None

def test_products_page(session):
    """Тест страницы товаров"""
    try:
        response = session.get(f"{BASE_URL}/admin/products", timeout=5)
        print(f"📋 Страница товаров: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Страница товаров доступна")
            return True
        else:
            print("❌ Страница товаров недоступна")
            return False
    except Exception as e:
        print(f"❌ Ошибка доступа к товарам: {e}")
        return False

def main():
    print("🌐 ТЕСТИРОВАНИЕ HTTP API АДМИНКИ")
    print("=" * 50)
    
    # Проверяем настройки
    print(f"📋 Настройки:")
    print(f"   URL: {BASE_URL}")
    print(f"   Админ: {ADMIN_USERNAME}")
    print(f"   Пароль: {'*' * len(ADMIN_PASSWORD)}")
    
    # Тестируем вход
    login_success, session = test_admin_login()
    
    if login_success and session:
        # Тестируем страницы
        products_success = test_products_page(session)
        
        if products_success:
            print("\n🎉 HTTP API работает корректно!")
            return 0
        else:
            print("\n❌ Проблемы с доступом к страницам")
            return 1
    else:
        print("\n❌ Не удалось войти в админку")
        return 1

if __name__ == "__main__":
    exit(main())
