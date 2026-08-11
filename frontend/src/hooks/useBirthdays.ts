import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { components } from '../api/client'
import { queryKeys } from '../lib/queryClient'

export type Birthday = components['schemas']['BirthdayResponse']
type BirthdayCreate = components['schemas']['BirthdayCreate']
type BirthdayUpdate = components['schemas']['BirthdayUpdate']

export function useBirthdays() {
  return useQuery({
    queryKey: queryKeys.birthdays,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/birthdays')
      if (error) throw new Error('Failed to load birthdays')
      return data
    },
  })
}

export function useUpcomingBirthdays(days: number) {
  return useQuery({
    queryKey: queryKeys.birthdayAlerts(days),
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/birthdays/upcoming', {
        params: { query: { days } },
      })
      if (error) throw new Error('Failed to load upcoming birthdays')
      return data
    },
  })
}

export function useCreateBirthday() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: BirthdayCreate) => {
      const { data, error } = await apiClient.POST('/api/birthdays', { body: payload })
      if (error) throw new Error('Failed to create birthday')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.birthdays })
      queryClient.invalidateQueries({ queryKey: ['birthday-alerts'] })
    },
  })
}

export function useUpdateBirthday() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: BirthdayUpdate }) => {
      const { data, error } = await apiClient.PUT('/api/birthdays/{birthday_id}', {
        params: { path: { birthday_id: id } },
        body,
      })
      if (error) throw new Error('Failed to update birthday')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.birthdays })
      queryClient.invalidateQueries({ queryKey: ['birthday-alerts'] })
    },
  })
}

export function useDeleteBirthday() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (birthdayId: string) => {
      const { error } = await apiClient.DELETE('/api/birthdays/{birthday_id}', {
        params: { path: { birthday_id: birthdayId } },
      })
      if (error) throw new Error('Failed to delete birthday')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.birthdays })
      queryClient.invalidateQueries({ queryKey: ['birthday-alerts'] })
    },
  })
}

export function useAutoCreateBirthdayExpenses() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await apiClient.POST('/api/birthdays/auto-create-expenses', {})
      if (error) throw new Error('Failed to auto-create birthday expenses')
      return data as { created: number }
    },
    onSuccess: () => {
      // Может создать расходы за текущий месяц — инвалидируем частичные ключи.
      queryClient.invalidateQueries({ queryKey: ['expense-items'] })
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}
