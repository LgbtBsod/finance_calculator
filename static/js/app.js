/**
 * Financial Calculator App - Main Application Logic
 * Apple-level UX with clean architecture
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════
    // STATE MANAGEMENT
    // ═══════════════════════════════════════════════════════════════

    const state = {
        settings: {
            baseSalary: 0,
            taxRate: 13,
            kef: 1,
            advanceCutoffDay: 15,
            isAdvanceDateInclusive: false,
            accountShortened: false,
            standardHours: 40,
            payoutDay1: 10,
            payoutDay2: 25,
            moveWeekendToFriday: false
        },
        expenseGroups: [],
        expenseItems: [],
        debts: []
    };

    let currentMonth = new Date().getMonth() + 1;
    let currentYear = new Date().getFullYear();

    // ═══════════════════════════════════════════════════════════════
    // DATE INITIALIZATION
    // ═══════════════════════════════════════════════════════════════

    function initDateSelects() {
        const monthSelect = document.getElementById('expense-item-month');
        const yearSelect = document.getElementById('expense-item-year');
        const analyticsMonthSelect = document.getElementById('analytics-month');
        const analyticsYearSelect = document.getElementById('analytics-year');

        const months = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ];

        // Заполняем селект расходов
        if (monthSelect) {
            months.forEach((name, index) => {
                const option = document.createElement('option');
                option.value = index + 1;
                option.textContent = name;
                if (index + 1 === currentMonth) option.selected = true;
                monthSelect.appendChild(option);
            });
        }

        const currentYr = new Date().getFullYear();
        if (yearSelect) {
            for (let y = currentYr - 1; y <= currentYr + 2; y++) {
                const option = document.createElement('option');
                option.value = y;
                option.textContent = y;
                if (y === currentYr) option.selected = true;
                yearSelect.appendChild(option);
            }
        }

        // Заполняем селект аналитики
        if (analyticsMonthSelect) {
            months.forEach((name, index) => {
                const option = document.createElement('option');
                option.value = index + 1;
                option.textContent = name;
                if (index + 1 === currentMonth) option.selected = true;
                analyticsMonthSelect.appendChild(option);
            });
        }

        if (analyticsYearSelect) {
            for (let y = currentYr - 1; y <= currentYr + 2; y++) {
                const option = document.createElement('option');
                option.value = y;
                option.textContent = y;
                if (y === currentYr) option.selected = true;
                analyticsYearSelect.appendChild(option);
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // API INTEGRATION
    // ═══════════════════════════════════════════════════════════════

    async function apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(`/api${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const colors = {
            success: 'var(--success)',
            error: 'var(--danger)',
            warning: 'var(--warning)',
            info: 'var(--primary)'
        };
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };

        toast.style.cssText = `
            position: fixed;
            top: calc(20px + var(--safe-area-top));
            right: 20px;
            background: white;
            padding: 16px 20px;
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-2xl);
            border-left: 4px solid ${colors[type] || colors.info};
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: var(--z-toast);
            animation: slideInRight 0.3s var(--ease-spring);
            max-width: 350px;
        `;

        toast.innerHTML = `
            <span style="font-size: 18px;">${icons[type] || icons.info}</span>
            <span style="color: var(--gray-800); font-weight: 500; font-size: 14px;">${message}</span>
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s var(--ease-in)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    async function loadSettings() {
        try {
            const settings = await apiCall('/settings');
            state.settings = settings;
            updateSettingsUI();
            updateBalanceUI();
            showApiStatus(true);
        } catch (error) {
            console.warn('Failed to load settings, using defaults');
            showApiStatus(false);
        }
    }

    async function loadExpenseGroups() {
        try {
            const groups = await apiCall('/expense-groups');
            state.expenseGroups = groups;
            renderExpenseGroups();
            updateGroupSelect();
        } catch (error) {
            console.warn('Failed to load expense groups');
        }
    }

    async function loadExpenseItems() {
        try {
            const items = await apiCall('/expense-items');
            state.expenseItems = items;
            renderExpenseItems();
        } catch (error) {
            console.warn('Failed to load expense items');
        }
    }

    async function addExpenseItemToAPI(data) {
        try {
            const item = await apiCall('/expense-items', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            state.expenseItems.push(item);
            renderExpenseItems();
            showToast('Расход успешно добавлен', 'success');
            return true;
        } catch (error) {
            showToast('Ошибка добавления расхода', 'error');
            return false;
        }
    }

    async function deleteExpenseItemToAPI(id) {
        try {
            await apiCall(`/expense-items/${id}`, { method: 'DELETE' });
            state.expenseItems = state.expenseItems.filter(item => item.id !== id);
            renderExpenseItems();
            showToast('Расход удалён', 'success');
            return true;
        } catch (error) {
            showToast('Ошибка удаления расхода', 'error');
            return false;
        }
    }

    async function loadDebts() {
        try {
            const debts = await apiCall('/debts');
            state.debts = debts;
            renderDebts();
        } catch (error) {
            console.warn('Failed to load debts');
        }
    }

    async function saveSettingsToAPI() {
        try {
            const updated = await apiCall('/settings', {
                method: 'PUT',
                body: JSON.stringify(state.settings)
            });
            state.settings = updated;
            showToast('Настройки сохранены', 'success');
        } catch (error) {
            showToast('Ошибка сохранения настроек', 'error');
        }
    }

    async function addExpenseGroupToAPI(name, color) {
        try {
            const group = await apiCall('/expense-groups', {
                method: 'POST',
                body: JSON.stringify({ name, color })
            });
            state.expenseGroups.push(group);
            renderExpenseGroups();
            updateGroupSelect();
            showToast('Группа расходов создана', 'success');
        } catch (error) {
            showToast('Ошибка создания группы', 'error');
        }
    }

    async function deleteExpenseGroupToAPI(id) {
        try {
            await apiCall(`/expense-groups/${id}`, { method: 'DELETE' });
            state.expenseGroups = state.expenseGroups.filter(g => g.id !== id);
            renderExpenseGroups();
            showToast('Группа удалена', 'success');
        } catch (error) {
            showToast('Ошибка удаления группы', 'error');
        }
    }

    async function addDebtToAPI(title, amount) {
        try {
            const debt = await apiCall('/debts', {
                method: 'POST',
                body: JSON.stringify({
                    title,
                    totalAmount: parseFloat(amount),
                    month: currentMonth,
                    year: currentYear
                })
            });
            state.debts.push(debt);
            renderDebts();
            showToast('Долг добавлен', 'success');
        } catch (error) {
            showToast('Ошибка добавления долга', 'error');
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // UI FUNCTIONS
    // ═══════════════════════════════════════════════════════════════

    function switchTab(tabId) {
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        document.getElementById(tabId).classList.add('active');
        
        // Find the button that triggered this and make it active
        const buttons = document.querySelectorAll('.tab-btn');
        buttons.forEach(btn => {
            if (btn.getAttribute('onclick').includes(tabId)) {
                btn.classList.add('active');
            }
        });

        // Refresh analytics when switching to analytics tab
        if (tabId === 'analytics') {
            loadAnalytics();
        }
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 0
        }).format(amount);
    }

    function updateSettingsUI() {
        const settings = state.settings;
        const elements = {
            'setting-base-salary': settings.baseSalary,
            'setting-tax-rate': settings.taxRate,
            'setting-kef': settings.kef,
            'setting-cutoff-day': settings.advanceCutoffDay,
            'setting-standard-hours': settings.standardHours,
            'setting-payout-day1': settings.payoutDay1 || 10,
            'setting-payout-day2': settings.payoutDay2 || 25
        };

        Object.entries(elements).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el && value !== undefined) {
                el.value = value;
            }
        });

        const moveWeekendEl = document.getElementById('setting-move-weekend');
        if (moveWeekendEl) {
            moveWeekendEl.checked = settings.moveWeekendToFriday || false;
        }
    }

    function updateBalanceUI() {
        const base = state.settings.baseSalary;
        const tax = state.settings.taxRate / 100;
        const kef = state.settings.kef;

        const afterTax = base * (1 - tax);
        const withKef = afterTax * kef;

        const elements = {
            'base-salary': withKef,
            'first-payment': withKef * 0.4,
            'second-payment': withKef * 0.6
        };

        Object.entries(elements).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = formatCurrency(value);
            }
        });

        const monthNames = [
            '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ];
        const periodEl = document.getElementById('period-display');
        if (periodEl) {
            periodEl.textContent = `Период: ${monthNames[currentMonth]} ${currentYear}`;
        }
    }

    function renderExpenseGroups() {
        const container = document.getElementById('expense-groups-list');
        if (!container) return;

        if (state.expenseGroups.length === 0) {
            container.innerHTML = '<p style="color: var(--gray-500); text-align: center; padding: 40px; grid-column: 1/-1;">📁 Нет групп расходов<br><span style="font-size: 13px; opacity: 0.7;">Создайте первую группу для категоризации расходов</span></p>';
            return;
        }

        container.innerHTML = state.expenseGroups.map(group => `
            <div class="card expense-group-card" style="border-left: 5px solid ${group.color}; background: white; color: #333; position: relative; transition: all 0.3s ease;">
                <button onclick="deleteExpenseGroup('${group.id}')" style="position: absolute; top: 10px; right: 10px; background: none; border: none; cursor: pointer; opacity: 0.5; transition: opacity 0.2s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.5'">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FF3B30" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                </button>
                <h3 style="color: ${group.color}; margin-right: 30px;">${group.name}</h3>
                <p style="font-size: 12px; opacity: 0.7;">💰 ${state.expenseItems.filter(item => item.groupId === group.id).length} расходов</p>
            </div>
        `).join('');
    }

    function updateGroupSelect() {
        const select = document.getElementById('expense-item-group');
        if (!select) return;

        const currentValue = select.value;
        select.innerHTML = '<option value="">Без группы</option>';
        
        state.expenseGroups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = group.name;
            option.style.color = group.color;
            select.appendChild(option);
        });

        if (currentValue && state.expenseGroups.some(g => g.id === currentValue)) {
            select.value = currentValue;
        }
    }

    function renderExpenseItems() {
        const container = document.getElementById('expense-items-list');
        if (!container) return;

        if (state.expenseItems.length === 0) {
            container.innerHTML = '<p style="color: #666; grid-column: 1/-1;">💸 Нет расходов<br><span style="font-size: 13px; opacity: 0.7;">Добавьте первый расход</span></p>';
            return;
        }

        container.innerHTML = state.expenseItems.map(item => {
            const group = state.expenseGroups.find(g => g.id === item.groupId);
            const groupName = group ? group.name : 'Без группы';
            const groupColor = group ? group.color : '#666';

            return `
            <div class="card white" style="border-left: 4px solid ${groupColor}; position: relative;">
                <button onclick="deleteExpenseItem('${item.id}')" style="position: absolute; top: 10px; right: 10px; background: none; border: none; cursor: pointer; opacity: 0.5; transition: opacity 0.2s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.5'">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FF3B30" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                </button>
                <h3 style="color: var(--gray-800); font-size: 16px; margin-right: 30px;">${item.name}</h3>
                <p class="amount" style="color: var(--danger); font-size: 20px;">${formatCurrency(item.amount)}</p>
                <div style="margin-top: 10px; font-size: 13px; opacity: 0.7;">
                    <span style="background: ${groupColor}; color: white; padding: 2px 8px; border-radius: 12px; margin-right: 5px;">${groupName}</span>
                    <span>${item.half === 1 ? '1-я пол.' : '2-я пол.'} • ${item.month}/${item.year}</span>
                    ${item.isRecurring ? '<span style="color: var(--primary); margin-left: 5px;">🔄 Повтор.</span>' : ''}
                </div>
            </div>
            `;
        }).join('');
    }

    function renderDebts() {
        const container = document.getElementById('debts-list');
        if (!container) return;

        if (state.debts.length === 0) {
            container.innerHTML = '<p style="color: #666; grid-column: 1/-1;">💳 Нет долгов<br><span style="font-size: 13px; opacity: 0.7;">Все долги погашены</span></p>';
            return;
        }

        container.innerHTML = state.debts.map(debt => `
            <div class="card orange" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <h3>${debt.title}</h3>
                <p class="amount">${formatCurrency(debt.totalAmount)}</p>
                <p style="margin-top: 10px; opacity: 0.8;">ID: ${debt.id.substring(0, 8)}...</p>
            </div>
        `).join('');
    }

    function showApiStatus(connected) {
        const indicator = document.getElementById('api-status-indicator');
        if (!indicator) return;

        if (connected) {
            indicator.innerHTML = '<span class="status-badge" style="background: #d4edda; color: #155724; padding: 8px 16px; border-radius: 20px; font-weight: 500; font-size: 14px;">✅ API подключено</span>';
        } else {
            indicator.innerHTML = '<span class="status-badge" style="background: #f8d7da; color: #721c24; padding: 8px 16px; border-radius: 20px; font-weight: 500; font-size: 14px;">⚠️ Режим офлайн</span>';
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // EVENT HANDLERS
    // ═══════════════════════════════════════════════════════════════

    function addExpenseGroup() {
        const nameInput = document.getElementById('expense-group-name');
        const colorInput = document.getElementById('expense-group-color');
        
        const name = nameInput ? nameInput.value.trim() : '';
        const color = colorInput ? colorInput.value : '#007AFF';

        if (!name) {
            showToast('Введите название группы', 'warning');
            return;
        }

        addExpenseGroupToAPI(name, color);
        
        if (nameInput) nameInput.value = '';
    }

    function addExpenseItem() {
        const nameInput = document.getElementById('expense-item-name');
        const amountInput = document.getElementById('expense-item-amount');
        const groupSelect = document.getElementById('expense-item-group');
        const halfSelect = document.getElementById('expense-item-half');
        const monthSelect = document.getElementById('expense-item-month');
        const yearSelect = document.getElementById('expense-item-year');
        const recurringCheckbox = document.getElementById('expense-item-recurring');

        const name = nameInput ? nameInput.value.trim() : '';
        const amount = amountInput ? parseFloat(amountInput.value) : 0;
        const groupId = groupSelect ? groupSelect.value || null : null;
        const half = halfSelect ? parseInt(halfSelect.value) : 1;
        const month = monthSelect ? parseInt(monthSelect.value) : currentMonth;
        const year = yearSelect ? parseInt(yearSelect.value) : currentYear;
        const isRecurring = recurringCheckbox ? recurringCheckbox.checked : false;

        if (!name || !amount || amount <= 0) {
            showToast('Введите корректное название и сумму расхода', 'warning');
            return;
        }

        addExpenseItemToAPI({
            name,
            amount,
            groupId,
            half,
            month,
            year,
            isRecurring
        });

        // Очистка формы
        if (nameInput) nameInput.value = '';
        if (amountInput) amountInput.value = '';
        if (recurringCheckbox) recurringCheckbox.checked = false;
    }

    function addDebt() {
        const titleInput = document.getElementById('debt-title');
        const amountInput = document.getElementById('debt-amount');

        const title = titleInput ? titleInput.value.trim() : '';
        const amount = amountInput ? parseFloat(amountInput.value) : 0;

        if (!title || !amount || amount <= 0) {
            showToast('Введите корректное название и сумму', 'warning');
            return;
        }

        addDebtToAPI(title, amount);
        
        if (titleInput) titleInput.value = '';
        if (amountInput) amountInput.value = '';
    }

    // ═══════════════════════════════════════════════════════════════
    // ANALYTICS FUNCTIONS
    // ═══════════════════════════════════════════════════════════════

    async function loadAnalytics() {
        const monthSelect = document.getElementById('analytics-month');
        const yearSelect = document.getElementById('analytics-year');
        
        const month = monthSelect ? parseInt(monthSelect.value) : currentMonth;
        const year = yearSelect ? parseInt(yearSelect.value) : currentYear;

        try {
            const response = await fetch(`/api/analytics/summary?month=${month}&year=${year}`);
            if (!response.ok) throw new Error('Failed to load analytics');

            const data = await response.json();

            // Обновляем общую сумму
            const totalEl = document.getElementById('analytics-total');
            const countEl = document.getElementById('analytics-count');
            
            if (totalEl) {
                totalEl.textContent = `₽ ${data.total.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
            if (countEl) {
                countEl.textContent = `${data.count} записей`;
            }

            // Рендерим категории
            const categoriesContainer = document.getElementById('analytics-categories');
            if (categoriesContainer) {
                if (data.categories && data.categories.length > 0) {
                    categoriesContainer.innerHTML = data.categories.map(cat => `
                        <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background: var(--gray-50); border-radius: var(--radius-md); transition: transform 0.2s var(--ease-out); cursor: default;" onmouseover="this.style.transform='translateX(4px)'" onmouseout="this.style.transform='translateX(0)'">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="width: 14px; height: 14px; border-radius: 50%; background: ${cat.color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"></div>
                                <span style="font-weight: 500; color: var(--gray-700); font-size: 15px;">${cat.name}</span>
                            </div>
                            <span style="font-weight: 600; color: var(--gray-900); font-feature-settings: 'tnum'; tabular-nums: tabular-nums;">₽ ${cat.amount.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        </div>
                    `).join('');
                } else {
                    categoriesContainer.innerHTML = `
                        <div style="text-align: center; padding: 40px 20px; color: var(--gray-500);">
                            <div style="font-size: 48px; margin-bottom: 12px; opacity: 0.5;">📊</div>
                            <p style="font-weight: 500;">Нет данных для отображения</p>
                            <p style="font-size: 13px; margin-top: 8px; opacity: 0.7;">Добавьте расходы или измените период</p>
                        </div>
                    `;
                }
            }
        } catch (error) {
            console.error('Error loading analytics:', error);
            showToast('Ошибка загрузки аналитики', 'error');
        }
    }

    function saveSettings() {
        const settingsMap = {
            'setting-base-salary': 'baseSalary',
            'setting-tax-rate': 'taxRate',
            'setting-kef': 'kef',
            'setting-cutoff-day': 'advanceCutoffDay',
            'setting-standard-hours': 'standardHours',
            'setting-payout-day1': 'payoutDay1',
            'setting-payout-day2': 'payoutDay2'
        };

        Object.entries(settingsMap).forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (el) {
                state.settings[key] = parseFloat(el.value) || 0;
            }
        });

        const moveWeekendEl = document.getElementById('setting-move-weekend');
        if (moveWeekendEl) {
            state.settings.moveWeekendToFriday = moveWeekendEl.checked;
        }

        saveSettingsToAPI();
        updateBalanceUI();
    }

    // ═══════════════════════════════════════════════════════════════
    // GLOBAL FUNCTIONS (exposed to window for HTML onclick handlers)
    // ═══════════════════════════════════════════════════════════════

    window.switchTab = switchTab;
    window.addExpenseGroup = addExpenseGroup;
    window.addExpenseItem = addExpenseItem;
    window.addDebt = addDebt;
    window.saveSettings = saveSettings;
    window.loadAnalytics = loadAnalytics;
    window.deleteExpenseGroup = function(id) {
        if (confirm('Вы уверены, что хотите удалить эту группу?')) {
            deleteExpenseGroupToAPI(id);
        }
    };
    window.deleteExpenseItem = function(id) {
        if (confirm('Вы уверены, что хотите удалить этот расход?')) {
            deleteExpenseItemToAPI(id);
        }
    };

    // ═══════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════

    async function init() {
        initDateSelects();
        await loadSettings();
        await loadExpenseGroups();
        await loadExpenseItems();
        await loadDebts();
        console.log('✅ Application initialized');
    }

    // Start the app when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
