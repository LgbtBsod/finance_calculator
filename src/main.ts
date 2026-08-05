/**
 * Main Application Entry Point
 * OpenUI5-inspired architecture with vanilla TypeScript
 * Integrated with Python FastAPI backend
 */

import { IAppState, IExpenseGroup, IExpenseItem, IDebt, IVacation, ISalarySettings } from './types';
import { getCurrentMonthYear, formatCurrency } from './utils/helpers';
import { createSwitch, createColorPicker, createDebtCard, createIncomeSection, createSettingsPanel } from './components';
import { expenseGroupsApi, expenseItemsApi, debtsApi, vacationsApi, settingsApi } from './api';

// ═══════════════════════════════════════════════════════════════
// APPLICATION STATE (SSOT)
// ═══════════════════════════════════════════════════════════════

const defaultSettings: ISalarySettings = {
  baseSalary: 100000,
  taxRate: 13,
  kef: 1.0,
  advanceCutoffDay: 15,
  isAdvanceDateInclusive: true,
  accountShortened: false,
  standardHours: 40,
};

const initialState: IAppState = {
  expenseGroups: [],
  expenseItems: [],
  debts: [],
  vacations: [],
  salarySettings: defaultSettings,
  selectedMonth: new Date().getMonth() + 1,
  selectedYear: new Date().getFullYear(),
};

let state: IAppState = { ...initialState };
let listeners: Array<(state: IAppState) => void> = [];

// ═══════════════════════════════════════════════════════════════
// STATE MANAGEMENT (Simple Store Pattern - SRP)
// ═══════════════════════════════════════════════════════════════

function setState<K extends keyof IAppState>(
  key: K,
  value: IAppState[K] | ((prev: IAppState[K]) => IAppState[K])
): void {
  const newValue = typeof value === 'function' 
    ? (value as Function)(state[key]) 
    : value;
  
  state = { ...state, [key]: newValue };
  notifyListeners();
}

function subscribe(listener: (state: IAppState) => void): () => void {
  listeners.push(listener);
  return () => {
    listeners = listeners.filter(l => l !== listener);
  };
}

function notifyListeners(): void {
  listeners.forEach(listener => listener(state));
}

function getState(): IAppState {
  return state;
}

// ═══════════════════════════════════════════════════════════════
// API INTEGRATION LAYER (SRP: Only handles data fetching)
// ═══════════════════════════════════════════════════════════════

async function loadFromBackend(): Promise<void> {
  try {
    // Load settings
    const settingsResult = await settingsApi.get();
    if (settingsResult.success && settingsResult.data) {
      setState('salarySettings', settingsResult.data);
    }

    // Load expense groups
    const groupsResult = await expenseGroupsApi.getAll();
    if (groupsResult.success && groupsResult.data) {
      setState('expenseGroups', groupsResult.data);
    }

    // Load expenses
    const { selectedMonth, selectedYear } = state;
    const expensesResult = await expenseItemsApi.getAll(selectedMonth, selectedYear);
    if (expensesResult.success && expensesResult.data) {
      setState('expenseItems', expensesResult.data);
    }

    // Load debts
    const debtsResult = await debtsApi.getAll(selectedMonth, selectedYear);
    if (debtsResult.success && debtsResult.data) {
      setState('debts', debtsResult.data);
    }

    // Load vacations
    const vacationsResult = await vacationsApi.getAll(selectedMonth, selectedYear);
    if (vacationsResult.success && vacationsResult.data) {
      setState('vacations', vacationsResult.data);
    }

    console.log('✅ Data loaded from backend');
  } catch (error) {
    console.warn('⚠️ Backend not available, using local state:', error);
  }
}

async function syncWithBackend(): Promise<void> {
  // In production, sync state changes to backend
  // For now, log the changes
  console.log('🔄 Syncing with backend...');
}

// ═══════════════════════════════════════════════════════════════
// UI RENDERING
// ═══════════════════════════════════════════════════════════════

function render(): void {
  const root = document.getElementById('app');
  if (!root) return;
  
  root.innerHTML = '';
  
  // Header
  const header = createHeader();
  root.appendChild(header);
  
  // Main content area
  const main = document.createElement('main');
  main.className = 'main-content';
  
  // Tabs navigation
  const tabs = createTabs();
  main.appendChild(tabs);
  
  // Tab content based on active tab
  const activeTab = getActiveTab();
  const tabContent = createTabContent(activeTab);
  main.appendChild(tabContent);
  
  root.appendChild(main);
}

function createHeader(): HTMLElement {
  const header = document.createElement('header');
  header.className = 'app-header';
  
  const title = document.createElement('h1');
  title.textContent = '💰 Личный финансовый калькулятор';
  
  const period = document.createElement('p');
  const { selectedMonth, selectedYear } = state;
  const monthNames = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
  ];
  period.textContent = `Период: ${monthNames[selectedMonth]} ${selectedYear}`;
  
  header.appendChild(title);
  header.appendChild(period);
  
  return header;
}

let activeTab: 'balance' | 'expenses' | 'debts' | 'settings' = 'balance';

function getActiveTab(): string {
  return activeTab;
}

function createTabs(): HTMLElement {
  const tabsContainer = document.createElement('div');
  tabsContainer.className = 'tabs-container';
  
  const tabs = [
    { id: 'balance', label: '📊 Баланс и ЗП' },
    { id: 'expenses', label: '💸 Расходы' },
    { id: 'debts', label: '💳 Долги' },
    { id: 'settings', label: '⚙️ Настройки' },
  ];
  
  tabs.forEach(tab => {
    const button = document.createElement('button');
    button.className = `tab-button ${activeTab === tab.id ? 'active' : ''}`;
    button.textContent = tab.label;
    button.addEventListener('click', () => {
      activeTab = tab.id as any;
      render();
    });
    tabsContainer.appendChild(button);
  });
  
  return tabsContainer;
}

function createTabContent(tabId: string): HTMLElement {
  const content = document.createElement('div');
  content.className = 'tab-content';
  
  switch (tabId) {
    case 'balance':
      content.appendChild(createBalanceTab());
      break;
    case 'expenses':
      content.appendChild(createExpensesTab());
      break;
    case 'debts':
      content.appendChild(createDebtsTab());
      break;
    case 'settings':
      content.appendChild(createSettingsTab());
      break;
  }
  
  return content;
}

function createBalanceTab(): HTMLElement {
  const tab = document.createElement('div');
  tab.className = 'balance-tab';
  
  // Income section (top right as requested)
  const incomeSection = createIncomeSection({
    vacations: state.vacations,
    onAddVacation: async (amount, date) => {
      const result = await vacationsApi.create({ totalAmount: amount, payoutDate: date });
      if (result.success && result.data) {
        setState('vacations', [...state.vacations, result.data]);
        syncWithBackend();
      }
    },
    onDeleteVacation: async (id) => {
      const result = await vacationsApi.delete(id);
      if (result.success) {
        setState('vacations', state.vacations.filter(v => v.id !== id));
        syncWithBackend();
      }
    },
  });
  tab.appendChild(incomeSection);
  
  // Balance cards would go here
  const balanceCards = document.createElement('div');
  balanceCards.className = 'balance-cards';
  balanceCards.innerHTML = `
    <div class="card">
      <h3>Итого начислено</h3>
      <p class="amount">${formatCurrency(state.salarySettings.baseSalary)}</p>
    </div>
    <div class="card">
      <h3>К выплате (1-я)</h3>
      <p class="amount">${formatCurrency(state.salarySettings.baseSalary * 0.4)}</p>
    </div>
    <div class="card">
      <h3>К выплате (2-я)</h3>
      <p class="amount">${formatCurrency(state.salarySettings.baseSalary * 0.6)}</p>
    </div>
  `;
  tab.appendChild(balanceCards);
  
  return tab;
}

function createExpensesTab(): HTMLElement {
  const tab = document.createElement('div');
  tab.className = 'expenses-tab';
  
  // Add expense group form
  const addGroupForm = document.createElement('div');
  addGroupForm.className = 'add-group-form';
  addGroupForm.innerHTML = '<h3>➕ Добавить группу расходов</h3>';
  
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.className = 'input';
  nameInput.placeholder = 'Название группы';
  
  let selectedColor = '#3b82f6';
  const colorPicker = createColorPicker({
    selectedColor: selectedColor,
    onSelectColor: (color) => { selectedColor = color; },
  });
  
  const addGroupBtn = document.createElement('button');
  addGroupBtn.className = 'btn btn-primary';
  addGroupBtn.textContent = '+ Добавить группу';
  addGroupBtn.addEventListener('click', async () => {
    if (nameInput.value.trim()) {
      const result = await expenseGroupsApi.create({ 
        name: nameInput.value.trim(), 
        color: selectedColor 
      });
      if (result.success && result.data) {
        setState('expenseGroups', [...state.expenseGroups, result.data]);
        nameInput.value = '';
        syncWithBackend();
        render();
      }
    }
  });
  
  addGroupForm.appendChild(nameInput);
  addGroupForm.appendChild(colorPicker);
  addGroupForm.appendChild(addGroupBtn);
  tab.appendChild(addGroupForm);
  
  // Expense groups list
  if (state.expenseGroups.length > 0) {
    const groupsList = document.createElement('div');
    groupsList.className = 'groups-list';
    
    state.expenseGroups.forEach(group => {
      const groupCard = document.createElement('div');
      groupCard.className = 'group-card';
      groupCard.style.borderLeftColor = group.color;
      groupCard.innerHTML = `
        <div class="group-header">
          <span class="color-dot" style="background-color: ${group.color}"></span>
          <h4>${group.name}</h4>
          <button class="btn btn-sm btn-danger delete-group">🗑️</button>
        </div>
      `;
      
      const deleteBtn = groupCard.querySelector('.delete-group');
      deleteBtn?.addEventListener('click', async () => {
        const result = await expenseGroupsApi.delete(group.id);
        if (result.success) {
          setState('expenseGroups', state.expenseGroups.filter(g => g.id !== group.id));
          syncWithBackend();
          render();
        }
      });
      
      groupsList.appendChild(groupCard);
    });
    
    tab.appendChild(groupsList);
  }
  
  return tab;
}

function createDebtsTab(): HTMLElement {
  const tab = document.createElement('div');
  tab.className = 'debts-tab';
  
  // Add debt form
  const addDebtForm = document.createElement('div');
  addDebtForm.className = 'add-debt-form';
  addDebtForm.innerHTML = '<h3>➕ Добавить долг</h3>';
  
  const titleInput = document.createElement('input');
  titleInput.type = 'text';
  titleInput.className = 'input';
  titleInput.placeholder = 'Название долга';
  
  const amountInput = document.createElement('input');
  amountInput.type = 'number';
  amountInput.className = 'input';
  amountInput.placeholder = 'Сумма долга';
  amountInput.min = '0';
  
  const addDebtBtn = document.createElement('button');
  addDebtBtn.className = 'btn btn-primary';
  addDebtBtn.textContent = '+ Добавить долг';
  addDebtBtn.addEventListener('click', async () => {
    if (titleInput.value.trim() && parseFloat(amountInput.value) > 0) {
      const result = await debtsApi.create({
        title: titleInput.value.trim(),
        totalAmount: parseFloat(amountInput.value),
        month: state.selectedMonth,
        year: state.selectedYear,
      });
      if (result.success && result.data) {
        setState('debts', [...state.debts, result.data]);
        titleInput.value = '';
        amountInput.value = '';
        syncWithBackend();
        render();
      }
    }
  });
  
  addDebtForm.appendChild(titleInput);
  addDebtForm.appendChild(amountInput);
  addDebtForm.appendChild(addDebtBtn);
  tab.appendChild(addDebtForm);
  
  // Debts list with multiple repayments support
  if (state.debts.length > 0) {
    const debtsList = document.createElement('div');
    debtsList.className = 'debts-list';
    
    state.debts.forEach(debt => {
      const debtCard = createDebtCard({
        debt,
        onAddRepayment: async (debtId, amount, date, note) => {
          const result = await debtsApi.addRepayment(debtId, { amount, date, note });
          if (result.success && result.data) {
            setState('debts', state.debts.map(d => {
              if (d.id === debtId) {
                return {
                  ...d,
                  repayments: [...d.repayments, result.data!],
                };
              }
              return d;
            }));
            syncWithBackend();
            render();
          }
        },
        onDeleteRepayment: async (debtId, repaymentId) => {
          const result = await debtsApi.deleteRepayment(debtId, repaymentId);
          if (result.success) {
            setState('debts', state.debts.map(d => {
              if (d.id === debtId) {
                return {
                  ...d,
                  repayments: d.repayments.filter(r => r.id !== repaymentId),
                };
              }
              return d;
            }));
            syncWithBackend();
            render();
          }
        },
        onDeleteDebt: async (id) => {
          const result = await debtsApi.delete(id);
          if (result.success) {
            setState('debts', state.debts.filter(d => d.id !== id));
            syncWithBackend();
            render();
          }
        },
      });
      debtsList.appendChild(debtCard);
    });
    
    tab.appendChild(debtsList);
  }
  
  return tab;
}

function createSettingsTab(): HTMLElement {
  const tab = document.createElement('div');
  tab.className = 'settings-tab';
  
  const settingsPanel = createSettingsPanel({
    settings: state.salarySettings,
    onUpdate: async (updates) => {
      const result = await settingsApi.update(updates);
      if (result.success && result.data) {
        setState('salarySettings', result.data);
        syncWithBackend();
      }
    },
  });
  
  tab.appendChild(settingsPanel);
  
  return tab;
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

async function init(): Promise<void> {
  // Load initial data from backend API
  await loadFromBackend();
  
  // Subscribe to state changes and re-render
  subscribe(() => render());
  
  // Initial render
  render();
  
  console.log('Application initialized with OpenUI5-inspired architecture');
  console.log('Following SOLID principles and SSOT pattern');
  console.log('Backend API integration: enabled');
}

// Start the application
init();
