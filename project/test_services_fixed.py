#!/usr/bin/env python3
"""
Исправленный скрипт для тестирования сервисов
"""
import sys
import os
sys.path.append('.')

def test_product_service():
    """Тест ProductService с правильными параметрами"""
    print("🔧 ТЕСТИРОВАНИЕ PRODUCT SERVICE")
    print("=" * 50)
    
    try:
        from app.services.product_service import ProductService
        print("✅ ProductService импортирован")
        
        # Создаём сервис с путём к файлу
        csv_path = "data/products.csv"
        service = ProductService(csv_path=csv_path)
        print(f"✅ ProductService создан с файлом: {csv_path}")
        
        # Тест загрузки товаров
        products = service.get_all_products()
        print(f"📦 Загружено товаров: {len(products)}")
        
        if products:
            print("\n📋 Первые 3 товара:")
            for i, product in enumerate(products[:3]):
                print(f"   {i+1}. {product.get('sku')} - {product.get('title')} - {product.get('price')}₽")
        
        # Тест категорий
        categories = service.get_categories()
        print(f"\n📂 Найдено категорий: {len(categories)}")
        print(f"   Категории: {categories}")
        
        # Тест поиска по SKU
        test_sku = 'PIA-001'
        product = service.get_product_by_sku(test_sku)
        if product:
            print(f"\n🔍 Товар {test_sku} найден: {product.get('title')}")
        else:
            print(f"\n❌ Товар {test_sku} не найден")
        
        # Тест валидации
        test_data = {
            'sku': 'TEST-VALIDATION',
            'title': 'Тест валидации',
            'price': '5990',
            'category': 'пиалы',
            'stock': '10'
        }
        
        errors = service.validate_product_data(test_data)
        if not errors:
            print(f"\n✅ Валидация тестовых данных прошла успешно")
        else:
            print(f"\n❌ Ошибки валидации: {errors}")
        
        # Тест создания товара
        print(f"\n➕ Тестирование создания товара...")
        create_result = service.create_product(test_data)
        if create_result:
            print("✅ Товар создан успешно")
            
            # Проверяем, что товар действительно создался
            created_product = service.get_product_by_sku('TEST-VALIDATION')
            if created_product:
                print("✅ Созданный товар найден в системе")
                
                # Тест редактирования
                print(f"\n✏️ Тестирование редактирования товара...")
                updated_data = test_data.copy()
                updated_data['title'] = 'Обновлённая тестовая пиала'
                updated_data['price'] = '6990'
                
                update_result = service.update_product('TEST-VALIDATION', updated_data)
                if update_result:
                    print("✅ Товар обновлён успешно")
                    
                    # Проверяем обновление
                    updated_product = service.get_product_by_sku('TEST-VALIDATION')
                    if updated_product and updated_product.get('title') == 'Обновлённая тестовая пиала':
                        print("✅ Изменения сохранены корректно")
                    else:
                        print("❌ Изменения не сохранились")
                else:
                    print("❌ Ошибка обновления товара")
                
                # Тест удаления
                print(f"\n🗑️ Тестирование удаления товара...")
                delete_result = service.delete_product('TEST-VALIDATION')
                if delete_result:
                    print("✅ Товар удалён успешно")
                    
                    # Проверяем удаление
                    deleted_product = service.get_product_by_sku('TEST-VALIDATION')
                    if not deleted_product:
                        print("✅ Товар действительно удалён из системы")
                        return True
                    else:
                        print("❌ Товар не удалён")
                        return False
                else:
                    print("❌ Ошибка удаления товара")
                    return False
            else:
                print("❌ Созданный товар не найден")
                return False
        else:
            print("❌ Ошибка создания товара")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ ТОВАРОВ (ИСПРАВЛЕННАЯ ВЕРСИЯ)")
    print("=" * 60)
    
    # Проверяем файл
    csv_file = "data/products.csv"
    if not os.path.exists(csv_file):
        print(f"❌ Файл {csv_file} не найден")
        return 1
    
    print(f"✅ Файл {csv_file} найден")
    
    # Тестируем сервис
    success = test_product_service()
    
    if success:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("Система создания и редактирования товаров работает корректно.")
        return 0
    else:
        print("\n❌ ТЕСТЫ ПРОВАЛЕНЫ")
        return 1

if __name__ == "__main__":
    sys.exit(main())
