/**
 * Utility functions - Don't Reinvent The Wheel
 * Using standard libraries and simple helpers
 */

/**
 * Generate unique ID using crypto.randomUUID (modern browsers)
 */
export const generateId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Format currency with Russian locale
 */
export const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
  }).format(amount);
};

/**
 * Format date to DD.MM.YYYY
 */
export const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
};

/**
 * Calculate remaining debt amount
 */
export const calculateRemainingDebt = (
  totalAmount: number, 
  repayments: Array<{ amount: number }>
): number => {
  const totalRepaid = repayments.reduce((sum, r) => sum + r.amount, 0);
  return Math.max(0, totalAmount - totalRepaid);
};

/**
 * Validate date string
 */
export const isValidDate = (dateString: string): boolean => {
  const date = new Date(dateString);
  return !isNaN(date.getTime());
};

/**
 * Clamp number between min and max
 */
export const clamp = (value: number, min: number, max: number): number => {
  return Math.min(Math.max(value, min), max);
};

/**
 * Get current month and year
 */
export const getCurrentMonthYear = (): { month: number; year: number } => {
  const now = new Date();
  return {
    month: now.getMonth() + 1, // 1-12
    year: now.getFullYear(),
  };
};

/**
 * Get month name in Russian
 */
export const getMonthName = (month: number): string => {
  const months = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
  ];
  return months[month] || '';
};

/**
 * Calculate half of month based on date
 */
export const getHalfOfMonth = (day: number): 1 | 2 => {
  return day <= 15 ? 1 : 2;
};

/**
 * Deep clone object
 */
export const deepClone = <T>(obj: T): T => {
  return JSON.parse(JSON.stringify(obj));
};
