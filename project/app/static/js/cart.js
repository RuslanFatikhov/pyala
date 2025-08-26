// Функциональность кнопки закрытия корзины
document.addEventListener('DOMContentLoaded', function() {
    const closeButton = document.querySelector('.button-close');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            window.history.back();
        });
    }
});

// Создание кастомного поп-апа
function createConfirmModal(title, message, onConfirm, onCancel) {
    // Удаляем существующий модал если есть
    const existingModal = document.querySelector('.modal-overlay');
    if (existingModal) {
        existingModal.remove();
    }

    // Создаем HTML модала
    const modalHTML = `
        <div class="modal-overlay" id="confirmModal">
            <div class="modal-content">
                <h3 class="modal-title">${title}</h3>
                <div class="modal-body">
                    <p class="modal-text">${message}</p>
                </div>
                <div class="modal-actions">
                    <button class="btn-large-color2" id="modalCancel">
                        Отмена
                    </button>
                    <button class="btn-large-color5" id="modalConfirm">
                        Удалить
                    </button>
                </div>
            </div>
        </div>
    `;

    // Добавляем модал в DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    const modal = document.getElementById('confirmModal');
    const confirmBtn = document.getElementById('modalConfirm');
    const cancelBtn = document.getElementById('modalCancel');

    // Показываем модал
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);

    // Обработчики событий
    confirmBtn.addEventListener('click', function() {
        hideModal();
        if (onConfirm) onConfirm();
    });

    cancelBtn.addEventListener('click', function() {
        hideModal();
        if (onCancel) onCancel();
    });

    // Закрытие по клику на фон
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            hideModal();
            if (onCancel) onCancel();
        }
    });

    // Закрытие по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            hideModal();
            if (onCancel) onCancel();
        }
    });

    function hideModal() {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove();
        }, 300);
    }
}

function updateQuantity(sku, newQty) {
    if (newQty < 1) {
        removeFromCart(sku);
        return;
    }
    
    fetch('/cart/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            sku: sku,
            qty: newQty
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            location.reload();
        } else {
            showNotification(data.error, 'error');
        }
    });
}

// ОБНОВЛЕНО: Используем кастомный поп-ап вместо confirm()
function removeFromCart(sku) {
    createConfirmModal(
        'Удалить товар?',
        'Вы уверены, что хотите удалить этот товар из корзины?',
        function() {
            // Подтверждение - удаляем товар
            fetch('/cart/remove', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sku: sku
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.ok) {
                    location.reload();
                    updateCartCounter();
                } else {
                    showNotification(data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error removing from cart:', error);
                showNotification('Ошибка удаления товара', 'error');
            });
        },
        function() {
            // Отмена - ничего не делаем
            console.log('Удаление отменено');
        }
    );
}