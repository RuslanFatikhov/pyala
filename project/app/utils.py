# В вашем Flask приложении (например, в utils.py или в основном файле)

import os
from flask import current_app

def get_product_images(sku, max_images=5):
    """
    Автоматически находит все изображения для товара по SKU
    Возвращает список путей к существующим изображениям
    """
    images = []
    base_path = os.path.join(current_app.static_folder, 'img')
    
    for i in range(1, max_images + 1):
        # Проверяем разные расширения
        for ext in ['jpg', 'jpeg', 'png', 'webp']:
            filename = f"{sku.lower()}_{i}.{ext}"
            filepath = os.path.join(base_path, filename)
            
            if os.path.exists(filepath):
                images.append(f"/static/img/{filename}")
                break  # Найдено изображение с этим номером, переходим к следующему
    
    return images

def get_product_main_image(sku):
    """
    Возвращает путь к главному изображению товара или заглушку
    """
    images = get_product_images(sku, max_images=1)
    return images[0] if images else "/static/img/no-image.jpg"

# Регистрируем функции как Jinja2 фильтры/функции
def register_template_functions(app):
    """
    Регистрирует функции для использования в шаблонах
    """
    @app.template_global()
    def product_images(sku, max_images=5):
        return get_product_images(sku, max_images)
    
    @app.template_global() 
    def product_main_image(sku):
        return get_product_main_image(sku)
    
    @app.template_filter()
    def image_exists(image_path):
        """
        Проверяет существование файла изображения
        """
        if not image_path or image_path.startswith('/static/img/no-image'):
            return False
            
        # Убираем /static/ из пути для проверки в файловой системе
        file_path = image_path.replace('/static/', '')
        full_path = os.path.join(current_app.static_folder, file_path.replace('img/', ''))
        return os.path.exists(full_path)