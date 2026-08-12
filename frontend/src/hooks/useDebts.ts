import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { extractErrorMessage } from '../lib/apiError'
import { queryKeys } from '../lib/queryClient'

export function useDebts() {
  return useQuery({
    queryKey: queryKeys.debts,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/debts')
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось загрузить долги'))
      return data
    },
  })
}

interface CreateDebtInput {
  title: string
  totalAmount: number
}

/** month/year не выбираются в UI — берутся из текущей даты в момент отправки. */
export function useCreateDebt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ title, totalAmount }: CreateDebtInput) => {
      const now = new Date()
      const { data, error } = await apiClient.POST('/api/debts', {
        body: {
          title,
          totalAmount,
          month: now.getMonth() + 1,
          year: now.getFullYear(),
        },
      })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось добавить долг'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.debts })
    },
  })
}

export function useDeleteDebt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (debtId: string) => {
      const { error } = await apiClient.DELETE('/api/debts/{debt_id}', {
        params: { path: { debt_id: debtId } },
      })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось удалить долг'))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.debts })
    },
  })
}

interface AddRepaymentInput {
  debtId: string
  amount: number
}

export function useAddRepayment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ debtId, amount }: AddRepaymentInput) => {
      const { data, error } = await apiClient.POST('/api/debts/{debt_id}/repayments', {
        params: { path: { debt_id: debtId } },
        body: {
          amount,
          date: new Date().toISOString().slice(0, 10),
        },
      })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось добавить платёж'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.debts })
    },
  })
}

export function useDeleteRepayment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (repaymentId: string) => {
      const { error } = await apiClient.DELETE('/api/debts/repayments/{repayment_id}', {
        params: { path: { repayment_id: repaymentId } },
      })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось удалить платёж'))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.debts })
    },
  })
}
