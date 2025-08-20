// Глобальные функции для работы с корзиной и уведомлениями

// Обновление счетчика корзины
function updateCartCounter() {
    fetch('/cart')
        .then(response => response.text())
        .then(html => {
            // Простой способ извлечь количество товаров из HTML
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const cartItems = doc.querySelectorAll('.cart-item');
            const count = cartItems.length;
            
            const counter = document.getElementById('cart-count');
            if (counter) {
                counter.textContent = `(${count})`;
            }
        })
        .catch(error => {
            console.error('Error updating cart counter:', error);
        });
}

// Показ уведомлений
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} notification`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        opacity: 0;
        transform: translateY(-20px);
        transition: all 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateY(0)';
    }, 100);
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// Добавление товара в корзину (универсальная функция)
function addToCart(sku, qty = 1) {
    fetch('/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            sku: sku,
            qty: qty
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            updateCartCounter();
            showNotification('Товар добавлен в корзину', 'success');
            
            // Аналитика для GA4
            if (typeof gtag !== 'undefined') {
                gtag('event', 'add_to_cart', {
                    currency: 'RUB',
                    value: data.cart_summary.total,
                    items: [{
                        item_id: sku,
                        quantity: qty
                    }]
                });
            }
        } else {
            showNotification(data.error || 'Ошибка добавления товара', 'error');
        }
    })
    .catch(error => {
        console.error('Error adding to cart:', error);
        showNotification('Ошибка добавления товара', 'error');
    });
}

// Ленивая загрузка изображений
document.addEventListener('DOMContentLoaded', function() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
});

// Обработка форм с AJAX (опционально)
function submitFormAjax(formElement, successCallback) {
    const formData = new FormData(formElement);
    
    fetch(formElement.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (successCallback) {
                successCallback(data);
            }
            showNotification(data.message || 'Успешно выполнено', 'success');
        } else {
            showNotification(data.error || 'Произошла ошибка', 'error');
        }
    })
    .catch(error => {
        console.error('Form submission error:', error);
        showNotification('Ошибка отправки формы', 'error');
    });
}

// Маска для телефона (простая)
document.addEventListener('DOMContentLoaded', function() {
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length > 0) {
                if (value[0] === '8') {
                    value = '7' + value.substring(1);
                }
                if (value[0] === '7') {
                    value = value.substring(0, 11);
                    const formatted = value.replace(/(\d{1})(\d{3})(\d{3})(\d{2})(\d{2})/, '+$1 ($2) $3-$4-$5');
                    e.target.value = formatted;
                }
            }
        });
    });
});