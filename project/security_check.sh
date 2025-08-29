#!/bin/bash
# Полная проверка системы безопасности

echo "🔐 ПРОВЕРКА СИСТЕМЫ БЕЗОПАСНОСТИ"
echo "================================="

echo ""
echo "📂 ПРОВЕРКА ФАЙЛОВОЙ СТРУКТУРЫ:"
[ -f ".env" ] && echo "✅ .env файл" || echo "❌ .env отсутствует"
[ -f "data/orders.csv" ] && echo "✅ orders.csv" || echo "❌ orders.csv отсутствует"
[ -f "data/products.csv" ] && echo "✅ products.csv" || echo "❌ products.csv отсутствует"
[ -f "app/services/encryption.py" ] && echo "✅ модуль шифрования" || echo "❌ модуль шифрования отсутствует"
[ -f "app/services/secure_orders.py" ] && echo "✅ модуль заказов" || echo "❌ модуль заказов отсутствует"

echo ""
echo "🔑 ПРОВЕРКА КЛЮЧЕЙ:"
if [ -f ".env" ]; then
    grep -q "DATA_ENCRYPTION_KEY=" .env && echo "✅ DATA_ENCRYPTION_KEY" || echo "❌ DATA_ENCRYPTION_KEY отсутствует"
    grep -q "ENCRYPTION_SALT=" .env && echo "✅ ENCRYPTION_SALT" || echo "❌ ENCRYPTION_SALT отсутствует"
    grep -q "SECRET_KEY=" .env && echo "✅ SECRET_KEY" || echo "❌ SECRET_KEY отсутствует"
fi

echo ""
echo "🔒 ПРАВА ДОСТУПА:"
ENV_PERMS=$(ls -la .env 2>/dev/null | cut -d' ' -f1)
echo "📄 .env права: $ENV_PERMS"
ORDERS_PERMS=$(ls -la data/orders.csv 2>/dev/null | cut -d' ' -f1)
echo "📄 orders.csv права: $ORDERS_PERMS"

echo ""
echo "📦 ЗАВИСИМОСТИ:"
source .venv/bin/activate 2>/dev/null
python -c "import cryptography; print('✅ cryptography:', cryptography.__version__)" 2>/dev/null || echo "❌ cryptography не установлен"
python -c "import portalocker; print('✅ portalocker установлен')" 2>/dev/null || echo "❌ portalocker не установлен"

echo ""
echo "📊 ДАННЫЕ:"
if [ -f "data/orders.csv" ]; then
    ORDER_COUNT=$(tail -n +2 data/orders.csv 2>/dev/null | wc -l | tr -d ' ')
    echo "📋 Заказов: $ORDER_COUNT"
    
    HEADER=$(head -1 data/orders.csv 2>/dev/null)
    if echo "$HEADER" | grep -q "name_enc"; then
        echo "🔐 Заказы ЗАШИФРОВАНЫ"
    else
        echo "⚠️ Заказы НЕ зашифрованы"
    fi
fi

echo ""
echo "🧪 ТЕСТ ШИФРОВАНИЯ:"
if [ -f "app/services/encryption.py" ]; then
    python -c "
import sys
sys.path.append('.')
try:
    from app.services.encryption import DataEncryption
    enc = DataEncryption()
    test = enc.encrypt_data('test')
    result = enc.decrypt_data(test)
    print('✅ Шифрование работает:', 'test' == result)
except Exception as e:
    print('❌ Ошибка шифрования:', e)
" 2>/dev/null
fi

echo ""
echo "💡 АДМИН ПАРОЛЬ:"
grep "ADMIN_PASSWORD=" .env 2>/dev/null || echo "❌ Пароль не найден"
