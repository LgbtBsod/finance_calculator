import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from '../api/client'
import { apiClient } from '../api/client'
import { extractErrorMessage } from '../lib/apiError'
import { queryKeys } from '../lib/queryClient'

export type VacationCreateInput = components['schemas']['VacationCreate']

export function useVacations() {
  return useQuery({
    queryKey: queryKeys.vacations,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/vacations', {})
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось загрузить отпускные'))
      return data
    },
  })
}

export function useCreateVacation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: VacationCreateInput) => {
      const { data, error } = await apiClient.POST('/api/vacations', { body: payload })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось добавить отпускные'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vacations })
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}

export function useDeleteVacation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (vacationId: string) => {
      const { error } = await apiClient.DELETE('/api/vacations/{vacation_id}', {
        params: { path: { vacation_id: vacationId } },
      })
      if (error) throw new Error(extractErrorMessage(error, 'Не удалось удалить отпускные'))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vacations })
      queryClient.invalidateQueries({ queryKey: ['balance'] })
    },
  })
}
