// Общие функции JavaScript

// Форматирование даты
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Форматирование чисел
function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

// Показать уведомление
function showNotification(message, type = 'info') {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Стили для уведомления
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        padding: 15px 20px;
        border-radius: 5px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 15px;
        min-width: 300px;
        max-width: 400px;
        animation: slideInRight 0.3s ease;
    `;
    
    // Анимация появления
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .notification-content {
            display: flex;
            align-items: center;
            gap: 10px;
            flex: 1;
        }
        
        .notification-close {
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            padding: 0;
            font-size: 14px;
            opacity: 0.7;
            transition: opacity 0.3s;
        }
        
        .notification-close:hover {
            opacity: 1;
        }
    `;
    
    document.head.appendChild(style);
    document.body.appendChild(notification);
    
    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOutRight 0.3s ease forwards';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }, 5000);
}

// Проверка подключения к API
function checkApiConnection() {
    return fetch('/api/categories')
        .then(response => response.ok)
        .catch(() => false);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем подключение к API
    checkApiConnection().then(isConnected => {
        if (!isConnected) {
            showNotification('Нет подключения к серверу API', 'error');
        }
    });
    
    // Добавляем эффекты наведения для всех карточек
    document.querySelectorAll('.template-card, .feature-card, .stat-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
});

// Валидация email
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Валидация телефона
function isValidPhone(phone) {
    const phoneRegex = /^[\+]?[0-9\s\-\(\)]{10,}$/;
    return phoneRegex.test(phone);
}

// Сохранение в локальное хранилище
function saveToLocalStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
        return true;
    } catch (e) {
        console.error('Ошибка сохранения в localStorage:', e);
        return false;
    }
}

// Загрузка из локального хранилища
function loadFromLocalStorage(key) {
    try {
        const data = localStorage.getItem(key);
        return data ? JSON.parse(data) : null;
    } catch (e) {
        console.error('Ошибка загрузки из localStorage:', e);
        return null;
    }
}

function generateDocument() {
    const form = document.getElementById('documentForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const documentName = document.getElementById('document_name').value;
    const formData = {};
    templateFields.forEach(field => {
        const input = document.getElementById(field.key) || 
                     document.querySelector(`[name="${field.key}"]`);
        
        if (input) {
            if (field.type === 'checkbox') {
                formData[field.key] = input.checked ? 'Да' : 'Нет';
            } else if (field.type === 'select') {
                formData[field.key] = input.value;
            } else {
                formData[field.key] = input.value;
            }
        }
    });
    
    const payload = {
        template_id: templateId,
        fields: formData,
        document_name: documentName || ''  // Добавляем имя документа
    };
}

// Копирование текста в буфер обмена
function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => showNotification('Текст скопирован в буфер обмена', 'success'))
        .catch(() => showNotification('Не удалось скопировать текст', 'error'));
}

// Открытие модального окна
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
}

// Закрытие модального окна
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}
