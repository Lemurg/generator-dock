// simple-nav.js - Упрощенное управление навигацией

// Функция обновления навигации
function updateNavigation() {
    fetch('/api/auth/check')
        .then(response => response.json())
        .then(data => {
            const authLink = document.getElementById('authNavLink');
            const authText = document.getElementById('authNavText');
            const dropdownMenu = document.getElementById('dropdownMenu');
            
            if (data.authenticated) {
                authText.textContent = data.user.username;
                authLink.href = '#';
                
                // Показываем dropdown при клике
                authLink.onclick = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    dropdownMenu.classList.toggle('show');
                    
                    // Закрытие при клике вне dropdown
                    setTimeout(() => {
                        document.addEventListener('click', closeDropdown);
                    }, 10);
                };
                
            } else {
                authText.textContent = 'Войти';
                authLink.href = '/auth';
                authLink.onclick = null;
                dropdownMenu.classList.remove('show');
            }
        })
        .catch(error => {
            console.error('Ошибка проверки аутентификации:', error);
        });
}

// Функция закрытия dropdown
function closeDropdown(e) {
    const dropdown = document.getElementById('userDropdown');
    const dropdownMenu = document.getElementById('dropdownMenu');
    
    if (dropdown && !dropdown.contains(e.target)) {
        dropdownMenu.classList.remove('show');
        document.removeEventListener('click', closeDropdown);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Обновляем навигацию
    updateNavigation();
    
    // Настройка кнопки выхода
    const logoutLink = document.getElementById('logoutLink');
    if (logoutLink) {
        logoutLink.onclick = function(e) {
            e.preventDefault();
            fetch('/api/auth/logout', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = '/';
                }
            })
            .catch(error => {
                console.error('Ошибка выхода:', error);
                window.location.href = '/';
            });
        };
    }
});

// Экспортируем функции
window.updateNavigation = updateNavigation;