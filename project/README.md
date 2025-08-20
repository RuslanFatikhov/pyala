# MVP Интернет-магазин керамических пиал

Минимально жизнеспособный интернет-магазин на Flask с хранением данных в CSV файлах.

## Возможности

- 📦 Каталог товаров с фильтрами и поиском
- 🛒 Корзина покупок
- 📝 Оформление заказов
- 📧 Email и Telegram уведомления
- 👨‍💼 Админ-панель для управления
- 📊 Аналитика событий
- 📱 Адаптивный дизайн

## Быстрый старт

### 1. Создание структуры проекта

Скопируйте и выполните в Terminal VSCode:

```bash
# создать дерево проекта
mkdir -p project/{app/{services,templates/{admin,partials},static/{css,js,img}},data/backups}
cd project

# файлы
touch app/__init__.py app/routes_public.py app/routes_admin.py \
      app/services/{products.py,orders.py,validators.py,notify.py} \
      app/templates/{base.html,home.html,catalog.html,product.html,cart.html,checkout.html,thankyou.html} \
      app/templates/admin/{login.html,dashboard.html,products_upload.html,orders_list.html} \
      app/static/css/styles.css app/static/js/app.js \
      data/products.csv data/orders.csv \
      config.py run.py requirements.txt .env.example index.wsgi README.md

# виртуальное окружение
python3 -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# зависимости
pip install Flask python3-dotenv portalocker email-validator gunicorn
pip freeze > requirements.txt
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
```
SECRET_KEY=your-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
# ... остальные настройки
```

### 3. Локальный запуск

```bash
# Разработка
python3 run.py

# Продакшн-режим локально
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Откройте http://localhost:5000 (или http://localhost:8000 для gunicorn)

## Структура проекта

```
project/
├── app/
│   ├── __init__.py              # Инициализация Flask приложения
│   ├── routes_public.py         # Публичные маршруты (каталог, корзина, заказы)
│   ├── routes_admin.py          # Админ маршруты
│   ├── services/
│   │   ├── products.py          # Работа с товарами (CSV кэш)
│   │   ├── orders.py            # Работа с заказами (потокобезопасная запись)
│   │   ├── validators.py        # Валидация форм и CSV
│   │   └── notify.py            # Email/Telegram уведомления
│   ├── templates/               # HTML шаблоны
│   └── static/                  # CSS, JS, изображения
├── data/
│   ├── products.csv             # База товаров
│   ├── orders.csv              # Заказы
│   └── backups/                # Автобэкапы при обновлении
├── config.py                   # Конфигурация
├── run.py                      # Запуск разработки
├── index.wsgi                  # Точка входа для WSGI серверов
└── requirements.txt            # Зависимости python3
```

## Админ-панель

Доступ: `/admin`

Возможности:
- Просмотр статистики
- Загрузка нового CSV товаров с валидацией
- Управление заказами
- Экспорт данных

## Формат данных

### products.csv
```csv
sku,title,price,old_price,category,volume_ml,color,images,stock,is_active,description
PIA-001,Пиала целадон 90 мл,5990,,пиалы,90,зелёный,"/static/img/pia001_1.jpg|/static/img/pia001_2.jpg",5,1,"Описание товара"
```

### orders.csv
```csv
order_id,created_at,name,phone,city,address,items,total,comment,status
100001,2025-08-10 14:22,Имя,+7...,Город,Адрес,"PIA-001:2|PIA-002:1",19970,"Комментарий",new
```

## Деплой на Timeweb

### 1. Подготовка файлов

Убедитесь что есть:
- `index.wsgi` - точка входа WSGI
- `.env` с производственными настройками
- `requirements.txt` с зависимостями

### 2. Загрузка на сервер

Загрузите проект в корневую папку через Git/SFTP.

### 3. Настройка в панели Timeweb

1. Выберите python3 3.10+
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Убедитесь что точка входа: `index.wsgi`
4. Настройте права на запись для папки `data/`:
   ```bash
   chmod -R 755 data
   ```

### 4. Проверка

Откройте `https://yourdomain.com/health` - должно вернуть `{"ok": true}`

## Особенности реализации

### Потокобезопасность
- Запись заказов с file locking (`portalocker`)
- Thread-safe кэш товаров с RLock

### Кэширование
- Товары кэшируются в памяти
- Автоматическая инвалидация при обновлении CSV

### Валидация
- DRY-RUN проверка CSV перед заменой
- Серверная валидация всех форм

### Безопасность
- CSRF защита админки
- Валидация размеров файлов
- Санитизация пользовательского ввода

## Аналитика

Поддерживаемые события:
- `view_item` - просмотр товара
- `add_to_cart` - добавление в корзину  
- `begin_checkout` - начало оформления
- `purchase_submit` - отправка заказа
- `purchase_ok` - успешный заказ

Для подключения GA4 добавьте в `.env`:
```
ANALYTICS_GA4_ID=G-XXXXXXXXXX
```

## Уведомления

### Email
Настройте SMTP в `.env`:
```
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
EMAIL_TO=orders@yourstore.com
```

### Telegram
Получите webhook URL и добавьте в `.env`:
```
TELEGRAM_WEBHOOK_URL=https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>
```

## Разработка

### Добавление товаров
1. Отредактируйте `data/products.csv`
2. Или загрузите через админку `/admin/products/upload`

### Тестирование заказов
1. Добавьте товары в корзину
2. Оформите заказ
3. Проверьте `data/orders.csv`
4. Проверьте уведомления

### Расширение функционала
- Модифицируйте `app/services/` для логики
- Добавьте маршруты в `routes_public.py` / `routes_admin.py`
- Обновите шаблоны в `templates/`

## Требования

- python3 3.10+
- Flask 2.3+
- Права на запись в папку `data/`

## Лицензия

MIT License - свободно используйте для коммерческих проектов.
```

## 9. Финальная проверка

### Тест-кейсы для проверки:

1. **Каталог и поиск**
   ```bash
   curl http://localhost:5000/catalog?q=пиала
   curl http://localhost:5000/catalog?category=пиалы&price_min=5000
   ```

2. **Добавление в корзину**
   ```bash
   curl -X POST http://localhost:5000/cart/add \
        -H "Content-Type: application/json" \
        -d '{"sku":"PIA-001","qty":2}'
   ```

3. **Админ доступ**
   - Откройте `/admin`
   - Войдите (admin/admin)
   - Попробуйте загрузить CSV

4. **Health check**
   ```bash
   curl http://localhost:5000/health
   # Должно вернуть: {"ok": true}
   ```

### Checklist деплоя:

- [ ] `index.wsgi` корректно импортирует `app as application`
- [ ] `.env` содержит все необходимые переменные
- [ ] `requirements.txt` установлен на сервере  
- [ ] Права на запись для `data/` настроены
- [ ] CSV файлы созданы и корректны
- [ ] Email/Telegram уведомления настроены (опционально)
- [ ] `/health` возвращает OK

Проект готов к использованию! 🎉