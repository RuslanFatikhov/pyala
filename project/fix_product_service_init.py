#!/usr/bin/env python3
import re

# Читаем файл routes_admin.py
with open('app/routes_admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Ищем строку инициализации ProductService
old_line = 'product_service = ProductService()'
new_line = 'product_service = ProductService(csv_path="data/products.csv")'

if old_line in content:
    content = content.replace(old_line, new_line)
    print(f"✅ Заменена инициализация: {old_line} -> {new_line}")
    
    # Сохраняем исправленный файл
    with open('app/routes_admin.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Файл routes_admin.py обновлен")
else:
    print("❌ Строка инициализации не найдена")
    print("Ищем строки с ProductService:")
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'ProductService' in line and '=' in line:
            print(f"  Строка {i+1}: {line}")
