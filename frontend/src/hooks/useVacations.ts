import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from '../api/client'
import { apiClient } from '../api/client'
import { queryKeys } from '../lib/queryClient'

export type VacationCreateInput = components['schemas']['VacationCreate']

/** Достаёт человекочитаемое сообщение из ошибки FastAPI ({ detail: string | ValidationError[] }). */
function extractErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.length > 0) return detail
  }
  return fallback
}

export function useVacations() {
  return useQuery({
    queryKey: queryKeys.vacations,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/vacations', {})
      if (error) throw new Error('Не удалось загрузить отпускные')
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
