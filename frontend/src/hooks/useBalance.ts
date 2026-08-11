import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { queryKeys } from '../lib/queryClient'

export function useBalance(month: number, year: number) {
  return useQuery({
    queryKey: queryKeys.balance(month, year),
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/balance', {
        params: { query: { month, year } },
      })
      if (error) throw new Error('Failed to load balance')
      return data
    },
  })
}
