import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

/** Ключи запросов — единое место, чтобы не рассинхронизировать инвалидацию (DRY). */
export const queryKeys = {
  settings: ['settings'] as const,
  balance: (month: number, year: number) => ['balance', month, year] as const,
  expenseGroups: ['expense-groups'] as const,
  expenseItems: (month: number | null, year: number | null) =>
    ['expense-items', month, year] as const,
  debts: ['debts'] as const,
  vacations: ['vacations'] as const,
  birthdays: ['birthdays'] as const,
  birthdayAlerts: (days: number) => ['birthday-alerts', days] as const,
  analytics: (month: number, year: number) => ['analytics', month, year] as const,
}
