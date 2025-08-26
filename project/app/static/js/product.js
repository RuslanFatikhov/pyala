// product.js - JavaScript для страницы товара

// Смена главного изображения
function changeMainImage(src, thumbnail) {
    // Обновляем все изображения с ID main-product-image (мобильное и десктопное)
    const allMainImages = document.querySelectorAll('#main-product-image');
    allMainImages.forEach(img => {
        img.src = src;
    });
    
    // Обновление активного thumbnail для всех версий
    document.querySelectorAll('.thumbnail').forEach(t => t.classList.remove('active'));
    thumbnail.classList.add('active');
}

// Добавление в корзину с PDP
function addToCartFromPDP(sku) {
    const quantity = 1; // Пока зафиксируем количество = 1
    
    fetch('/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            sku: sku,
            qty: quantity
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            updateCartCounter();
            showNotification('Товар добавлен в корзину', 'success');
        } else {
            showNotification(data.error || 'Ошибка добавления товара', 'error');
        }
    })
    .catch(error => {
        console.error('Error adding to cart:', error);
        showNotification('Ошибка добавления товара', 'error');
    });
}

// Переключение мобильных вкладок
function showTabMobile(tabName) {
    // Скрываем все мобильные вкладки
    document.querySelectorAll('.product_mobile .tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Убираем активный класс с мобильных кнопок
    document.querySelectorAll('.product_mobile .tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Показываем нужную мобильную вкладку
    const targetTab = document.getElementById(tabName + '-tab-mobile');
    if (targetTab) {
        targetTab.classList.add('active');
    }
    
    // Активируем кнопку
    event.target.classList.add('active');
}

// Переключение десктопных вкладок
function showTabDesktop(tabName) {
    // Скрываем все десктопные вкладки
    document.querySelectorAll('.product_desktop .tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Убираем активный класс с десктопных кнопок
    document.querySelectorAll('.product_desktop .tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Показываем нужную десктопную вкладку
    const targetTab = document.getElementById(tabName + '-tab-desktop');
    if (targetTab) {
        targetTab.classList.add('active');
    }
    
    // Активируем кнопку
    event.target.classList.add('active');
}