/**
 * SSOT - Single Source of Truth for all type definitions
 * Following SOLID principles: Clear interfaces for each domain
 */

// ═══════════════════════════════════════════════════════════════
// EXPENSE GROUPS (with color grouping support)
// ═══════════════════════════════════════════════════════════════

export interface IExpenseGroup {
  id: string;
  name: string;
  color: string;
  parentId?: string; // For nested grouping
  sortOrder: number;
}

// ═══════════════════════════════════════════════════════════════
// EXPENSE ITEMS (with inclusive date support)
// ═══════════════════════════════════════════════════════════════

export interface IExpenseItem {
  id: string;
  groupId: string;
  name: string;
  amount: number;
  date: string;
  isInclusive: boolean; // Date inclusive flag for advance cutoff
  half: 1 | 2; // First or second half of month
  isRecurring: boolean;
  month: number;
  year: number;
}

// ═══════════════════════════════════════════════════════════════
// DEBTS & REPAYMENTS (multiple repayments per debt)
// ═══════════════════════════════════════════════════════════════

export interface IDebt {
  id: string;
  title: string;
  totalAmount: number;
  repayments: IRepayment[];
  createdAt: string;
  month: number;
  year: number;
}

export interface IRepayment {
  id: string;
  debtId: string;
  amount: number;
  date: string;
  note?: string;
}

// ═══════════════════════════════════════════════════════════════
// INCOME (moved to top right as requested)
// ═══════════════════════════════════════════════════════════════

export interface IVacation {
  id: string;
  totalAmount: number;
  payoutDate: string;
}

export interface ISalarySettings {
  baseSalary: number;
  taxRate: number;
  kef: number;
  advanceCutoffDay: number;
  isAdvanceDateInclusive: boolean; // NEW: inclusive switch
  accountShortened: boolean;
  standardHours: number;
}

// ═══════════════════════════════════════════════════════════════
// APP STATE
// ═══════════════════════════════════════════════════════════════

export interface IAppState {
  expenseGroups: IExpenseGroup[];
  expenseItems: IExpenseItem[];
  debts: IDebt[];
  vacations: IVacation[];
  salarySettings: ISalarySettings;
  selectedMonth: number;
  selectedYear: number;
}

export type TabType = 'balance' | 'expenses' | 'debts' | 'vacations' | 'settings';

// ═══════════════════════════════════════════════════════════════
// API RESPONSE TYPES (for Python backend communication)
// ═══════════════════════════════════════════════════════════════

export interface IApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export type ExpenseGroupDTO = Omit<IExpenseGroup, 'sortOrder'>;
export type ExpenseItemDTO = Omit<IExpenseItem, 'id'>;
export type DebtDTO = Omit<IDebt, 'repayments' | 'createdAt'> & {
  repayments?: IRepayment[];
};
export type RepaymentDTO = Omit<IRepayment, 'id' | 'debtId'>;
