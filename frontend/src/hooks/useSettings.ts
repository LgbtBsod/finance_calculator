import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, type components } from '../api/client'
import { extractErrorMessage } from '../lib/apiError'
import { queryKeys } from '../lib/queryClient'

export type SettingsUpdatePayload = components['schemas']['SalarySettingsUpdate']

export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/settings')
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось загрузить настройки'))
      return data
    },
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: SettingsUpdatePayload) => {
      const { data, error } = await apiClient.PUT('/api/settings', { body: payload })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось обновить настройки'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings })
      // Изменение настроек зарплаты влияет на баланс всех периодов, поэтому
      // инвалидируем весь префикс ['balance'], а не только текущий месяц/год.
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}
