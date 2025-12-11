/**
 * Django CRM Modern Admin JavaScript
 * Улучшения UX для админки
 */

(function() {
    'use strict';

    // Ожидание загрузки DOM
    document.addEventListener('DOMContentLoaded', function() {
        initModernAdmin();
    });

    /**
     * Основная инициализация
     */
    function initModernAdmin() {
        // Добавляем fade-in анимацию для контента
        addFadeInAnimations();
        
        // Улучшаем формы
        enhanceForms();
        
        // Добавляем горячие клавиши
        addKeyboardShortcuts();
        
        // Улучшаем таблицы
        enhanceTables();
        
        // Добавляем автосохранение
        addAutoSave();
        
        // Улучшаем поиск
        enhanceSearch();
        
        // Добавляем быстрые действия
        addQuickActions();

        console.log('🎉 Modern Admin UI инициализирован');
    }

    /**
     * Добавление анимаций появления
     */
    function addFadeInAnimations() {
        const elements = document.querySelectorAll('.module, .messagelist li, table');
        elements.forEach((el, index) => {
            el.style.animationDelay = `${index * 50}ms`;
            el.classList.add('fade-in');
        });
    }

    /**
     * Улучшение форм
     */
    function enhanceForms() {
        // Добавляем валидацию в реальном времени
        const inputs = document.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            // Автофокус на первое поле
            if (input === inputs[0]) {
                input.focus();
            }

            // Валидация при изменении
            input.addEventListener('input', function() {
                validateField(this);
            });

            // Подсказки для полей
            addFieldHints(input);
        });

        // Улучшаем кнопки отправки
        const submitButtons = document.querySelectorAll('input[type="submit"], button[type="submit"]');
        submitButtons.forEach(btn => {
            btn.addEventListener('click', function(e) {
                // Показываем состояние загрузки
                showLoadingState(this);
                
                // Предотвращаем двойную отправку
                if (this.dataset.submitting === 'true') {
                    e.preventDefault();
                    return false;
                }
                this.dataset.submitting = 'true';
            });
        });
    }

    /**
     * Валидация поля
     */
    function validateField(field) {
        const value = field.value.trim();
        const isRequired = field.hasAttribute('required');
        const isValid = field.checkValidity();

        // Удаляем старые классы
        field.classList.remove('field-valid', 'field-invalid');

        if (value && isValid) {
            field.classList.add('field-valid');
        } else if (isRequired && (!value || !isValid)) {
            field.classList.add('field-invalid');
        }
    }

    /**
     * Добавление подсказок к полям
     */
    function addFieldHints(field) {
        const label = field.parentElement.querySelector('label');
        if (!label) return;

        // Добавляем счетчик символов для textarea
        if (field.tagName === 'TEXTAREA') {
            addCharacterCounter(field);
        }

        // Добавляем индикатор обязательности
        if (field.hasAttribute('required') && !label.querySelector('.required-indicator')) {
            const indicator = document.createElement('span');
            indicator.className = 'required-indicator';
            indicator.textContent = ' *';
            indicator.style.color = 'var(--error-color)';
            label.appendChild(indicator);
        }
    }

    /**
     * Счетчик символов для textarea
     */
    function addCharacterCounter(textarea) {
        const maxLength = textarea.getAttribute('maxlength');
        if (!maxLength) return;

        const counter = document.createElement('div');
        counter.className = 'character-counter';
        counter.style.cssText = `
            font-size: var(--font-size-sm);
            color: var(--text-muted);
            text-align: right;
            margin-top: var(--spacing-1);
        `;

        textarea.parentElement.appendChild(counter);

        const updateCounter = () => {
            const remaining = maxLength - textarea.value.length;
            counter.textContent = `${textarea.value.length}/${maxLength}`;
            counter.style.color = remaining < 50 ? 'var(--warning-color)' : 'var(--text-muted)';
        };

        textarea.addEventListener('input', updateCounter);
        updateCounter();
    }

    /**
     * Состояние загрузки для кнопки
     */
    function showLoadingState(button) {
        const originalText = button.textContent;
        button.dataset.originalText = originalText;
        button.textContent = '⏳ Сохраняем...';
        button.disabled = true;

        // Возвращаем состояние через 10 секунд (на случай ошибки)
        setTimeout(() => {
            if (button.dataset.submitting === 'true') {
                button.textContent = originalText;
                button.disabled = false;
                button.dataset.submitting = 'false';
            }
        }, 10000);
    }

    /**
     * Горячие клавиши
     */
    function addKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + S для сохранения
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                const submitBtn = document.querySelector('input[type="submit"], button[type="submit"]');
                if (submitBtn) {
                    submitBtn.click();
                    showToast('💾 Сохраняем форму...', 'info');
                }
            }

            // Ctrl/Cmd + K для фокуса на поиск
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchField = document.querySelector('#searchbar, input[name="q"]');
                if (searchField) {
                    searchField.focus();
                    searchField.select();
                }
            }

            // ESC для закрытия модальных окон
            if (e.key === 'Escape') {
                const modals = document.querySelectorAll('.modal, .popup');
                modals.forEach(modal => {
                    if (modal.style.display !== 'none') {
                        modal.style.display = 'none';
                    }
                });
            }
        });
    }

    /**
     * Улучшение таблиц
     */
    function enhanceTables() {
        const tables = document.querySelectorAll('table');
        tables.forEach(table => {
            // Добавляем сортировку по клику на заголовок
            addTableSorting(table);
            
            // Добавляем фильтрацию
            addTableFiltering(table);
            
            // Выделение строк
            addRowHighlighting(table);
        });
    }

    /**
     * Сортировка таблицы
     */
    function addTableSorting(table) {
        const headers = table.querySelectorAll('th');
        headers.forEach((header, index) => {
            if (header.textContent.trim() && !header.querySelector('input')) {
                header.style.cursor = 'pointer';
                header.title = 'Нажмите для сортировки';
                
                header.addEventListener('click', () => {
                    sortTable(table, index);
                    showToast('📊 Таблица отсортирована', 'success');
                });
            }
        });
    }

    /**
     * Функция сортировки таблицы
     */
    function sortTable(table, columnIndex) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));
        const isNumeric = rows.every(row => {
            const cell = row.cells[columnIndex];
            const text = cell ? cell.textContent.trim() : '';
            return !text || !isNaN(parseFloat(text));
        });

        rows.sort((a, b) => {
            const aVal = a.cells[columnIndex]?.textContent.trim() || '';
            const bVal = b.cells[columnIndex]?.textContent.trim() || '';

            if (isNumeric) {
                return parseFloat(aVal) - parseFloat(bVal);
            }
            return aVal.localeCompare(bVal, 'ru');
        });

        // Переключаем направление сортировки
        if (table.dataset.lastSort === columnIndex.toString()) {
            rows.reverse();
            table.dataset.lastSort = '';
        } else {
            table.dataset.lastSort = columnIndex.toString();
        }

        // Вставляем отсортированные строки
        rows.forEach(row => tbody.appendChild(row));
    }

    /**
     * Выделение строк таблицы
     */
    function addRowHighlighting(table) {
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.addEventListener('click', function() {
                // Убираем выделение с других строк
                rows.forEach(r => r.classList.remove('row-selected'));
                // Выделяем текущую строку
                this.classList.add('row-selected');
            });
        });
    }

    /**
     * Автосохранение
     */
    function addAutoSave() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            const formId = form.id || `form-${Date.now()}`;
            const inputs = form.querySelectorAll('input, textarea, select');
            
            // Восстанавливаем данные из localStorage
            restoreFormData(formId, inputs);
            
            // Сохраняем данные при изменении
            inputs.forEach(input => {
                input.addEventListener('input', debounce(() => {
                    saveFormData(formId, inputs);
                }, 1000));
            });

            // Очищаем сохраненные данные после успешной отправки
            form.addEventListener('submit', () => {
                clearFormData(formId);
            });
        });
    }

    /**
     * Сохранение данных формы
     */
    function saveFormData(formId, inputs) {
        const data = {};
        inputs.forEach(input => {
            if (input.name && input.value) {
                data[input.name] = input.value;
            }
        });
        
        try {
            localStorage.setItem(`form-data-${formId}`, JSON.stringify(data));
            showToast('💾 Данные автоматически сохранены', 'info', 1000);
        } catch (e) {
            console.warn('Не удалось сохранить данные формы:', e);
        }
    }

    /**
     * Восстановление данных формы
     */
    function restoreFormData(formId, inputs) {
        try {
            const saved = localStorage.getItem(`form-data-${formId}`);
            if (saved) {
                const data = JSON.parse(saved);
                inputs.forEach(input => {
                    if (input.name && data[input.name]) {
                        input.value = data[input.name];
                    }
                });
                showToast('📋 Данные формы восстановлены', 'info');
            }
        } catch (e) {
            console.warn('Не удалось восстановить данные формы:', e);
        }
    }

    /**
     * Очистка сохраненных данных формы
     */
    function clearFormData(formId) {
        try {
            localStorage.removeItem(`form-data-${formId}`);
        } catch (e) {
            console.warn('Не удалось очистить данные формы:', e);
        }
    }

    /**
     * Улучшение поиска
     */
    function enhanceSearch() {
        const searchInputs = document.querySelectorAll('#searchbar, input[name="q"]');
        searchInputs.forEach(input => {
            // Добавляем placeholder с подсказкой
            if (!input.placeholder) {
                input.placeholder = 'Поиск... (Ctrl+K)';
            }

            // Добавляем автодополнение
            addSearchAutocomplete(input);
        });
    }

    /**
     * Автодополнение для поиска
     */
    function addSearchAutocomplete(input) {
        const suggestions = [];
        const dropdown = document.createElement('div');
        dropdown.className = 'search-dropdown';
        dropdown.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            display: none;
            max-height: 200px;
            overflow-y: auto;
        `;

        input.parentElement.style.position = 'relative';
        input.parentElement.appendChild(dropdown);

        input.addEventListener('input', debounce(function() {
            const query = this.value.trim();
            if (query.length >= 2) {
                // Здесь можно добавить AJAX запрос для получения подсказок
                // Пока просто показываем сохраненные поисковые запросы
                showSearchSuggestions(dropdown, query, suggestions);
            } else {
                dropdown.style.display = 'none';
            }
        }, 300));

        // Скрываем dropdown при клике вне поля
        document.addEventListener('click', function(e) {
            if (!input.parentElement.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    }

    /**
     * Показ подсказок поиска
     */
    function showSearchSuggestions(dropdown, query, suggestions) {
        const filtered = suggestions.filter(s => 
            s.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 5);

        if (filtered.length === 0) {
            dropdown.style.display = 'none';
            return;
        }

        dropdown.innerHTML = filtered.map(suggestion => 
            `<div class="search-suggestion" style="padding: var(--spacing-2) var(--spacing-3); cursor: pointer; border-bottom: 1px solid var(--border-color);">
                ${suggestion}
            </div>`
        ).join('');

        dropdown.style.display = 'block';

        // Добавляем обработчики клика на подсказки
        dropdown.querySelectorAll('.search-suggestion').forEach(item => {
            item.addEventListener('click', function() {
                dropdown.previousElementSibling.value = this.textContent;
                dropdown.style.display = 'none';
            });
        });
    }

    /**
     * Быстрые действия
     */
    function addQuickActions() {
        // Добавляем floating action button
        const fab = document.createElement('div');
        fab.className = 'floating-action-button';
        fab.innerHTML = '⚡';
        fab.style.cssText = `
            position: fixed;
            bottom: var(--spacing-8);
            right: var(--spacing-8);
            width: 56px;
            height: 56px;
            background: var(--primary-color);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: var(--font-size-xl);
            cursor: pointer;
            box-shadow: var(--shadow-xl);
            transition: all var(--transition-fast);
            z-index: 1000;
        `;

        fab.addEventListener('click', showQuickActionsMenu);
        fab.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
        });
        fab.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });

        document.body.appendChild(fab);
    }

    /**
     * Меню быстрых действий
     */
    function showQuickActionsMenu() {
        const actions = [
            { icon: '➕', text: 'Добавить запись', action: () => window.location.href += 'add/' },
            { icon: '📊', text: 'Экспорт данных', action: () => showToast('🔄 Готовим экспорт...', 'info') },
            { icon: '🔄', text: 'Обновить страницу', action: () => window.location.reload() },
            { icon: '❓', text: 'Справка', action: () => window.open('/admin/doc/', '_blank') }
        ];

        showActionMenu(actions);
    }

    /**
     * Показ меню действий
     */
    function showActionMenu(actions) {
        // Удаляем существующее меню
        const existingMenu = document.querySelector('.action-menu');
        if (existingMenu) {
            existingMenu.remove();
            return;
        }

        const menu = document.createElement('div');
        menu.className = 'action-menu';
        menu.style.cssText = `
            position: fixed;
            bottom: var(--spacing-16);
            right: var(--spacing-8);
            background: var(--bg-color);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-xl);
            z-index: 1001;
            min-width: 200px;
            overflow: hidden;
            animation: fadeIn var(--transition-fast) ease-out;
        `;

        menu.innerHTML = actions.map(action => `
            <div class="action-item" style="
                padding: var(--spacing-3) var(--spacing-4);
                cursor: pointer;
                transition: background var(--transition-fast);
                display: flex;
                align-items: center;
                gap: var(--spacing-3);
            " data-action="${action.text}">
                <span style="font-size: var(--font-size-lg);">${action.icon}</span>
                <span>${action.text}</span>
            </div>
        `).join('');

        document.body.appendChild(menu);

        // Добавляем обработчики
        menu.querySelectorAll('.action-item').forEach((item, index) => {
            item.addEventListener('click', () => {
                actions[index].action();
                menu.remove();
            });
            
            item.addEventListener('mouseenter', function() {
                this.style.background = 'var(--bg-secondary)';
            });
            
            item.addEventListener('mouseleave', function() {
                this.style.background = 'transparent';
            });
        });

        // Закрываем меню при клике вне его
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target) && !e.target.closest('.floating-action-button')) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 100);
    }

    /**
     * Показ уведомлений (тостов)
     */
    function showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const colors = {
            success: 'var(--success-color)',
            warning: 'var(--warning-color)',
            error: 'var(--error-color)',
            info: 'var(--info-color)'
        };

        toast.style.cssText = `
            position: fixed;
            top: var(--spacing-8);
            right: var(--spacing-8);
            background: var(--bg-color);
            color: var(--text-color);
            padding: var(--spacing-4) var(--spacing-5);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            border-left: 4px solid ${colors[type] || colors.info};
            z-index: 10000;
            max-width: 300px;
            animation: slideInRight var(--transition-fast) ease-out;
            cursor: pointer;
        `;

        toast.textContent = message;

        // Удаляем toast при клике
        toast.addEventListener('click', () => toast.remove());

        document.body.appendChild(toast);

        // Автоматически удаляем toast
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'slideOutRight var(--transition-fast) ease-in';
                setTimeout(() => toast.remove(), 150);
            }
        }, duration);
    }

    /**
     * Debounce функция для ограничения частоты вызовов
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Добавляем стили для анимаций
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        .field-valid {
            border-color: var(--success-color) !important;
            box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.1) !important;
        }
        
        .field-invalid {
            border-color: var(--error-color) !important;
            box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1) !important;
        }
        
        .row-selected {
            background-color: var(--primary-light) !important;
        }
        
        .search-suggestion:hover {
            background-color: var(--bg-secondary);
        }
    `;
    document.head.appendChild(style);

  // Communication helpers (Marketing CRM)
  window.comm = window.comm || {};
  function getCSRFToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
  function collectPhones(btn){
    const d = btn.closest('.comm-toolbar');
    if (!d) return [];
    const cands = [d.dataset.mobile, d.dataset.phone, d.dataset.otherPhone, d.dataset.companyPhone, d.dataset.companyPhone2]
      .filter(Boolean)
      .map(s=>s.trim())
      .filter((v,i,a)=>v && a.indexOf(v)===i);
    return cands;
  }
  window.comm.clickToCall = function(btn){
    const phones = collectPhones(btn);
    if (!phones.length) { showToast('Нет номера для звонка','warning'); return; }
    const num = phones.length===1 ? phones[0] : prompt('Выберите номер для звонка:', phones.join(', '));
    if (!num) return;
    window.open(`/voip/get-callback/?number=${encodeURIComponent(num)}`,'_blank');
  }
  function resolveSmsChannelName(btn){
    const d = btn.closest('.comm-toolbar');
    let name = d?.dataset.smsChannelName || null;
    if (!name && window.COMM_DEFAULTS && window.COMM_DEFAULTS.sms_channel_name) name = window.COMM_DEFAULTS.sms_channel_name;
    if (!name){
      try { name = localStorage.getItem('smsChannelName'); } catch(e) {}
    }
    if (!name){
      name = prompt('Название SMS канала (ChannelAccount.name):');
      if (name){ try { localStorage.setItem('smsChannelName', name); } catch(e) {} }
    }
    return name || null;
  }
  window.comm.sendSMS = function(btn){
    const phones = collectPhones(btn);
    if (!phones.length) { showToast('Нет номера для SMS','warning'); return; }
    const to = phones.length===1 ? phones[0] : prompt('Кому отправить (номер из списка):', phones.join(', '));
    if (!to) return;
    const text = prompt('Текст SMS:');
    if (!text) return;
    const channel_name = resolveSmsChannelName(btn);
    if (!channel_name) { showToast('Не указан SMS канал','error'); return; }
    fetch('/integrations/sms/send/', {
      method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':getCSRFToken()},
      body: JSON.stringify({channel_name, to, text})
    }).then(r=>r.json()).then(_=>showToast('SMS отправлено','success')).catch(_=>showToast('Ошибка SMS','error'));
  }
  window.comm.sendBroadcast = function(btn){
    const list = prompt('Введите номера через запятую:');
    if (!list) return;
    const text = prompt('Текст SMS для рассылки:');
    if (!text) return;
    const channel_name = resolveSmsChannelName(btn);
    if (!channel_name) { showToast('Не указан SMS канал','error'); return; }
    const numbers = list.split(',').map(s=>s.trim()).filter(Boolean);
    numbers.forEach(to=>{
      fetch('/integrations/sms/send/', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':getCSRFToken()},
        body: JSON.stringify({channel_name, to, text, async:true})
      }).catch(()=>{});
    });
    showToast('Рассылка поставлена в очередь','info');
  }
  window.comm.sendTelegram = function(btn){
    const d = btn.closest('.comm-toolbar');
    let username = d?.dataset.telegram || '';
    if (!username) username = prompt('Telegram @username (без @):') || '';
    const text = prompt('Сообщение в Telegram:');
    if (!username || !text) return;
    fetch('/integrations/telegram/send/', {
      method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':getCSRFToken()},
      body: JSON.stringify({username, text})
    }).then(r=>r.json()).then(_=>showToast('Telegram сообщение поставлено','success')).catch(_=>showToast('Ошибка Telegram','error'));
  }
  window.comm.sendInstagram = function(btn){
    const d = btn.closest('.comm-toolbar');
    let handle = d?.dataset.instagram || '';
    if (!handle) handle = prompt('Instagram @handle (без @):') || '';
    const text = prompt('Сообщение в Instagram:');
    if (!handle || !text) return;
    fetch('/integrations/instagram/send/', {
      method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':getCSRFToken()},
      body: JSON.stringify({handle, text})
    }).then(r=>r.json()).then(_=>showToast('Instagram DM поставлено','success')).catch(_=>showToast('Ошибка Instagram','error'));
  }
})();