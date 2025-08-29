#!/usr/bin/env python3
"""
Простой скрипт для тестирования админки
"""
import sys
import os
sys.path.append('.')

def test_direct_service_calls():
    """Тестирование сервисов напрямую без HTTP"""
    print("🔧 ТЕСТИРОВАНИЕ СЕРВИСОВ НАПРЯМУЮ")
    print("=" * 50)
    
    try:
        from app.services.product_service import ProductService
        
        service = ProductService()
        
        # Тест 1: Загрузка товаров
        print("\n1️⃣ Тест загрузки товаров:")
        products = service.get_all_products()
        print(f"   Загружено: {len(products)} товаров")
        
        if products:
            print("   ✅ Товары загружены успешно")
            for i, product in enumerate(products[:3]):  # Показываем первые 3
                print(f"   {i+1}. {product.get('sku')} - {product.get('title')} - {product.get('price')}₽")
        else:
            print("   ❌ Товары не загружены")
            return False
        
        # Тест 2: Создание товара
        print("\n2️⃣ Тест создания товара:")
        test_product_data = {
            'sku': 'CLI-TEST-001',
            'title': 'CLI Тестовая пиала',
            'description': 'Создано через тестирование',
            'category': 'пиалы',
            'price': '5990',
            'stock': '10',
            'is_active': True,
            'color': 'белый',
            'volume_ml': '90'
        }
        
        # Проверяем валидацию
        errors = service.validate_product_data(test_product_data)
        if errors:
            print(f"   ❌ Ошибки валидации: {errors}")
            return False
        
        # Создаём товар
        success = service.create_product(test_product_data)
        if success:
            print("   ✅ Товар создан успешно")
        else:
            print("   ❌ Ошибка создания товара")
            return False
        
        # Тест 3: Поиск созданного товара
        print("\n3️⃣ Тест поиска созданного товара:")
        found_product = service.get_product_by_sku('CLI-TEST-001')
        if found_product:
            print(f"   ✅ Товар найден: {found_product.get('title')}")
        else:
            print("   ❌ Созданный товар не найден")
            return False
        
        # Тест 4: Редактирование товара
        print("\n4️⃣ Тест редактирования товара:")
        updated_data = test_product_data.copy()
        updated_data['title'] = 'CLI Обновлённая пиала'
        updated_data['price'] = '6990'
        
        edit_errors = service.validate_product_data(updated_data, 'CLI-TEST-001')
        if edit_errors:
            print(f"   ❌ Ошибки валидации при редактировании: {edit_errors}")
            return False
        
        edit_success = service.update_product('CLI-TEST-001', updated_data)
        if edit_success:
            print("   ✅ Товар обновлён успешно")
            
            # Проверяем обновление
            updated_product = service.get_product_by_sku('CLI-TEST-001')
            if updated_product and updated_product.get('title') == 'CLI Обновлённая пиала':
                print("   ✅ Изменения сохранены корректно")
            else:
                print("   ❌ Изменения не сохранились")
                return False
        else:
            print("   ❌ Ошибка обновления товара")
            return False
        
        # Тест 5: Удаление товара
        print("\n5️⃣ Тест удаления товара:")
        delete_success = service.delete_product('CLI-TEST-001')
        if delete_success:
            print("   ✅ Товар удалён успешно")
            
            # Проверяем удаление
            deleted_product = service.get_product_by_sku('CLI-TEST-001')
            if not deleted_product:
                print("   ✅ Товар действительно удалён")
            else:
                print("   ❌ Товар не удалён из системы")
                return False
        else:
            print("   ❌ Ошибка удаления товара")
            return False
        
        print("\n🎉 Все тесты пройдены успешно!")
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_operations():
    """Проверка файловых операций"""
    print("\n📁 ТЕСТИРОВАНИЕ ФАЙЛОВЫХ ОПЕРАЦИЙ")
    print("=" * 50)
    
    # Проверяем файл товаров
    products_file = "data/products.csv"
    if os.path.exists(products_file):
        print(f"✅ Файл {products_file} существует")
        
        # Читаем файл
        try:
            with open(products_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"   Строк в файле: {len(lines)}")
                print(f"   Заголовки: {lines[0].strip()}")
        except Exception as e:
            print(f"❌ Ошибка чтения файла: {e}")
            return False
    else:
        print(f"❌ Файл {products_file} не найден")
        return False
    
    # Проверяем права на запись
    try:
        test_file = "data/test_write.tmp"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("✅ Права на запись в папку data/ есть")
    except Exception as e:
        print(f"❌ Нет прав на запись в папку data/: {e}")
        return False
    
    return True

def main():
    print("🧪 ТЕСТИРОВАНИЕ АДМИНКИ ТОВАРОВ (ПРЯМЫЕ ВЫЗОВЫ)")
    print("=" * 60)
    
    # Тестируем файловые операции
    file_test_success = test_file_operations()
    
    if file_test_success:
        # Тестируем сервисы
        service_test_success = test_direct_service_calls()
        
        if service_test_success:
            print("\n🎊 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            print("Система создания и редактирования товаров работает корректно.")
            return 0
        else:
            print("\n❌ ТЕСТЫ СЕРВИСОВ ПРОВАЛЕНЫ")
            return 1
    else:
        print("\n❌ ТЕСТЫ ФАЙЛОВЫХ ОПЕРАЦИЙ ПРОВАЛЕНЫ")
        return 1

if __name__ == "__main__":
    sys.exit(main())
