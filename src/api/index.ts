/**
 * API Service Layer - Communication with Python backend
 * SRP: Only handles HTTP requests and response parsing
 */

import { 
  IApiResponse, 
  IExpenseGroup, 
  IExpenseItem, 
  IDebt, 
  IRepayment,
  IVacation,
  ISalarySettings 
} from '../types';

const API_BASE = '/api';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi<T>(
  endpoint: string, 
  options?: RequestInit
): Promise<IApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error('API Error:', error);
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// EXPENSE GROUPS API
// ═══════════════════════════════════════════════════════════════

export const expenseGroupsApi = {
  getAll: () => fetchApi<IExpenseGroup[]>('/expense-groups'),
  
  create: (data: { name: string; color: string; parentId?: string }) =>
    fetchApi<IExpenseGroup>('/expense-groups', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  update: (id: string, updates: Partial<IExpenseGroup>) =>
    fetchApi<IExpenseGroup>(`/expense-groups/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),
  
  delete: (id: string) =>
    fetchApi<void>(`/expense-groups/${id}`, {
      method: 'DELETE',
    }),
};

// ═══════════════════════════════════════════════════════════════
// EXPENSE ITEMS API
// ═══════════════════════════════════════════════════════════════

export const expenseItemsApi = {
  getAll: (month?: number, year?: number) => {
    const params = new URLSearchParams();
    if (month !== undefined) params.append('month', String(month));
    if (year !== undefined) params.append('year', String(year));
    return fetchApi<IExpenseItem[]>(`/expense-items?${params}`);
  },
  
  create: (data: Omit<IExpenseItem, 'id'>) =>
    fetchApi<IExpenseItem>('/expense-items', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  update: (id: string, updates: Partial<IExpenseItem>) =>
    fetchApi<IExpenseItem>(`/expense-items/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),
  
  delete: (id: string) =>
    fetchApi<void>(`/expense-items/${id}`, {
      method: 'DELETE',
    }),
};

// ═══════════════════════════════════════════════════════════════
// DEBTS API (with multiple repayments support)
// ═══════════════════════════════════════════════════════════════

export const debtsApi = {
  getAll: (month?: number, year?: number) => {
    const params = new URLSearchParams();
    if (month !== undefined) params.append('month', String(month));
    if (year !== undefined) params.append('year', String(year));
    return fetchApi<IDebt[]>(`/debts?${params}`);
  },
  
  create: (data: { title: string; totalAmount: number; month: number; year: number }) =>
    fetchApi<IDebt>('/debts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  addRepayment: (debtId: string, repayment: { amount: number; date: string; note?: string }) =>
    fetchApi<IRepayment>(`/debts/${debtId}/repayments`, {
      method: 'POST',
      body: JSON.stringify(repayment),
    }),
  
  updateRepayment: (debtId: string, repaymentId: string, updates: Partial<IRepayment>) =>
    fetchApi<IRepayment>(`/debts/${debtId}/repayments/${repaymentId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),
  
  deleteRepayment: (debtId: string, repaymentId: string) =>
    fetchApi<void>(`/debts/${debtId}/repayments/${repaymentId}`, {
      method: 'DELETE',
    }),
  
  delete: (id: string) =>
    fetchApi<void>(`/debts/${id}`, {
      method: 'DELETE',
    }),
};

// ═══════════════════════════════════════════════════════════════
// VACATIONS API (Income section - top right)
// ═══════════════════════════════════════════════════════════════

export const vacationsApi = {
  getAll: (month?: number, year?: number) => {
    const params = new URLSearchParams();
    if (month !== undefined) params.append('month', String(month));
    if (year !== undefined) params.append('year', String(year));
    return fetchApi<IVacation[]>(`/vacations?${params}`);
  },
  
  create: (data: { totalAmount: number; payoutDate: string }) =>
    fetchApi<IVacation>('/vacations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  delete: (id: string) =>
    fetchApi<void>(`/vacations/${id}`, {
      method: 'DELETE',
    }),
};

// ═══════════════════════════════════════════════════════════════
// SETTINGS API (with inclusive date switch)
// ═══════════════════════════════════════════════════════════════

export const settingsApi = {
  get: () => fetchApi<ISalarySettings>('/settings'),
  
  update: (updates: Partial<ISalarySettings>) =>
    fetchApi<ISalarySettings>('/settings', {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),
};
