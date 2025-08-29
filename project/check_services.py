#!/usr/bin/env python3
"""
Проверка работы сервисов приложения
"""
import sys
import os
sys.path.append('.')

try:
    from app.services.product_service import ProductService
    print("✅ ProductService импортирован")
    
    # Создаём экземпляр сервиса
    service = ProductService()
    
    # Проверяем загрузку товаров
    products = service.get_all_products()
    print(f"📦 Загружено товаров: {len(products)}")
    
    if products:
        first_product = products[0]
        print(f"   Первый товар: {first_product.get('sku')} - {first_product.get('title')}")
        print(f"   Цена: {first_product.get('price')}")
        print(f"   Остаток: {first_product.get('stock')}")
    
    # Проверяем категории
    categories = service.get_categories()
    print(f"📂 Категории: {categories}")
    
    # Тест валидации
    test_data = {
        'sku': 'TEST-VALIDATION',
        'title': 'Тест валидации',
        'price': '5990'
    }
    
    errors = service.validate_product_data(test_data)
    print(f"�� Валидация тестовых данных: {'✅ OK' if not errors else '❌ Ошибки: ' + str(errors)}")
    
    # Тест поиска товара по SKU
    test_product = service.get_product_by_sku('PIA-001')
    if test_product:
        print(f"🔍 Поиск товара PIA-001: ✅ Найден - {test_product.get('title')}")
    else:
        print("🔍 Поиск товара PIA-001: ❌ Не найден")
    
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
except Exception as e:
    print(f"❌ Ошибка работы сервиса: {e}")
