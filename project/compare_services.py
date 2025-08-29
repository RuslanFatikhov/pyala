#!/usr/bin/env python3
import sys
sys.path.append('.')

# Тест 1: ProductService как в веб-приложении
print("1. Тест ProductService() как в веб-приложении:")
try:
    from app.services.products import ProductService
    web_service = ProductService()  # Без параметров, как в веб-коде
    products = web_service.get_all_products()
    print(f"   Товаров загружено: {len(products)}")
    print("   ✅ Веб-сервис работает")
except Exception as e:
    print(f"   ❌ Ошибка веб-сервиса: {e}")

# Тест 2: ProductService с путём
print("\n2. Тест ProductService(csv_path) как в наших тестах:")
try:
    from app.services.product_service import ProductService
    direct_service = ProductService(csv_path="data/products.csv")
    products = direct_service.get_all_products()
    print(f"   Товаров загружено: {len(products)}")
    print("   ✅ Прямой сервис работает")
except Exception as e:
    print(f"   ❌ Ошибка прямого сервиса: {e}")

# Тест 3: Сравнение валидации
print("\n3. Сравнение валидации:")
test_data = {
    'sku': 'COMPARE-TEST',
    'title': 'Сравнительный тест',
    'price': '1000',
    'category': 'тест'
}

try:
    web_errors = web_service.validate_product_data(test_data)
    print(f"   Веб-валидация: {web_errors}")
except Exception as e:
    print(f"   ❌ Ошибка веб-валидации: {e}")

try:
    direct_errors = direct_service.validate_product_data(test_data)
    print(f"   Прямая валидация: {direct_errors}")
except Exception as e:
    print(f"   ❌ Ошибка прямой валидации: {e}")
