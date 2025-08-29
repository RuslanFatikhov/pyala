# app/template_helpers.py
"""
Вспомогательные функции для использования в шаблонах Jinja2
"""
import os
from flask import current_app

def find_product_images(sku: str, max_images: int = 10) -> list:
    """
    Находит все изображения товара по SKU в папке static/img/goods
    Возвращает список путей к изображениям или заглушку
    """
    if not sku:
        return ['/static/img/goods/no-image.jpg']
    
    images = []
    
    # Определяем путь к папке с изображениями
    goods_path = os.path.join(current_app.static_folder, 'img', 'goods')
    
    if not os.path.exists(goods_path):
        return ['/static/img/goods/no-image.jpg']
    
    # Получаем список всех файлов в папке
    try:
        all_files = os.listdir(goods_path)
    except OSError:
        return ['/static/img/goods/no-image.jpg']
    
    # Ищем файлы по паттерну SKU_X.jpg (в любом регистре)
    sku_lower = sku.lower()
    for i in range(1, max_images + 1):
        target_filename = f"{sku_lower}_{i}.jpg"
        
        # Ищем файл с учетом разного регистра
        found_file = None
        for filename in all_files:
            if filename.lower() == target_filename:
                found_file = filename
                break
        
        if found_file:
            images.append(f'/static/img/goods/{found_file}')
    
    # Если изображения не найдены, возвращаем заглушку
    if not images:
        return ['/static/img/goods/no-image.jpg']
    
    return images

def get_main_product_image(sku: str) -> str:
    """
    Возвращает основное изображение товара (первое найденное)
    """
    images = find_product_images(sku, max_images=1)
    return images[0] if images else '/static/img/goods/no-image.jpg'

def register_template_functions(app):
    """
    Регистрирует функции как глобальные функции в шаблонах Jinja2
    Вызывать в create_app()
    """
    
    @app.template_global()
    def product_images(sku, max_images=10):
        """Получить все изображения товара по SKU"""
        return find_product_images(sku, max_images)
    
    @app.template_global()
    def product_main_image(sku):
        """Получить основное изображение товара"""
        return get_main_product_image(sku)
    
    @app.template_filter()
    def image_exists(image_path):
        """
        Проверяет существование изображения
        Использование в шаблоне: {{ image_url | image_exists }}
        """
        if not image_path or 'no-image' in image_path:
            return False
            
        # Убираем /static/ из пути для проверки в файловой системе
        if image_path.startswith('/static/'):
            file_path = image_path[8:]  # убираем '/static/'
            full_path = os.path.join(current_app.static_folder, file_path)
            return os.path.exists(full_path)
        
        return False