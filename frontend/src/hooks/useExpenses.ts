import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { components } from '../api/client'
import { queryKeys } from '../lib/queryClient'

export type ExpenseGroup = components['schemas']['ExpenseGroupResponse']
export type ExpenseItem = components['schemas']['ExpenseItemResponse']
export type ExpenseGroupCreate = components['schemas']['ExpenseGroupCreate']
export type ExpenseItemCreate = components['schemas']['ExpenseItemCreate']
export type ExpenseGroupUpdate = components['schemas']['ExpenseGroupUpdate']
export type ExpenseItemUpdate = components['schemas']['ExpenseItemUpdate']

export function useExpenseGroups() {
  return useQuery({
    queryKey: queryKeys.expenseGroups,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/expense-groups')
      if (error) throw new Error('Failed to load expense groups')
      return data
    },
  })
}

export function useCreateExpenseGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ExpenseGroupCreate) => {
      const { data, error } = await apiClient.POST('/api/expense-groups', { body })
      if (error) throw new Error('Failed to create expense group')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.expenseGroups })
    },
  })
}

export function useUpdateExpenseGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: ExpenseGroupUpdate }) => {
      const { data, error } = await apiClient.PUT('/api/expense-groups/{group_id}', {
        params: { path: { group_id: id } },
        body,
      })
      if (error) throw new Error('Failed to update expense group')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.expenseGroups })
    },
  })
}

export function useDeleteExpenseGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (groupId: string) => {
      const { error } = await apiClient.DELETE('/api/expense-groups/{group_id}', {
        params: { path: { group_id: groupId } },
      })
      if (error) throw new Error('Failed to delete expense group')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.expenseGroups })
    },
  })
}

/** month/year оба null -> запрос без фильтра периода (все расходы). */
export function useExpenseItems(month: number | null, year: number | null) {
  return useQuery({
    queryKey: queryKeys.expenseItems(month, year),
    queryFn: async () => {
      const query = month != null && year != null ? { month, year } : {}
      const { data, error } = await apiClient.GET('/api/expense-items', {
        params: { query },
      })
      if (error) throw new Error('Failed to load expense items')
      return data
    },
  })
}

export function useCreateExpenseItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ExpenseItemCreate) => {
      const { data, error } = await apiClient.POST('/api/expense-items', { body })
      if (error) throw new Error('Failed to create expense item')
      return data
    },
    onSuccess: () => {
      // Частичные ключи — инвалидируют все запросы expense-items/balance независимо от их аргументов.
      queryClient.invalidateQueries({ queryKey: ['expense-items'] })
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}

export function useUpdateExpenseItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: ExpenseItemUpdate }) => {
      const { data, error } = await apiClient.PUT('/api/expense-items/{item_id}', {
        params: { path: { item_id: id } },
        body,
      })
      if (error) throw new Error('Failed to update expense item')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-items'] })
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}

export function useDeleteExpenseItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (itemId: string) => {
      const { error } = await apiClient.DELETE('/api/expense-items/{item_id}', {
        params: { path: { item_id: itemId } },
      })
      if (error) throw new Error('Failed to delete expense item')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-items'] })
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}
