import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { queryKeys } from '../lib/queryClient'

export function useAnalyticsSummary(month: number, year: number) {
  return useQuery({
    queryKey: queryKeys.analytics(month, year),
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/analytics/summary', {
        params: { query: { month, year } },
      })
      if (error) throw new Error('Failed to load analytics summary')
      return data
    },
  })
}
