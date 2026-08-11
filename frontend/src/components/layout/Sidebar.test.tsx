import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { apiClient } from '../../api/client'
import { Sidebar } from './Sidebar'

vi.mock('../../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
  },
}))

const mockedGet = apiClient.GET as unknown as ReturnType<typeof vi.fn>

const sampleBalance = {
  month: 8,
  year: 2026,
  netSalary: 87000,
  advance: 34800,
  payout: 52200,
  vacationHalf1: 0,
  vacationHalf2: 0,
  totalAccrued: 87000,
  toPayHalf1: 34800,
  toPayHalf2: 52200,
  expensesHalf1: 5000,
  expensesHalf2: 0,
  balanceHalf1: 29800,
  balanceHalf2: 52200,
  calculationMethod: 'proportional',
  workingDaysHalf1: null,
  workingDaysHalf2: null,
  workingDaysTotal: null,
  advanceCutoffDay: null,
  payoutDate1: '2026-08-10',
  payoutDate2: '2026-08-25',
  payoutDate1Nominal: '2026-08-10',
  payoutDate2Nominal: '2026-08-25',
}

const sampleAnalytics = {
  total: 5000,
  count: 2,
  categories: [{ name: 'Продукты', amount: 5000, color: '#FF0000' }],
}

function renderSidebar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Sidebar', () => {
  it('shows balance and analytics summaries for the current month', async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path === '/api/balance') return Promise.resolve({ data: sampleBalance, error: undefined })
      if (path === '/api/analytics/summary')
        return Promise.resolve({ data: sampleAnalytics, error: undefined })
      return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
    })

    renderSidebar()

    expect(await screen.findByText('К выплате (1-я половина)')).toBeInTheDocument()
    expect(screen.getByText('К выплате (2-я половина)')).toBeInTheDocument()
    expect(screen.getByText('Продукты')).toBeInTheDocument()

    const now = new Date()
    expect(mockedGet).toHaveBeenCalledWith('/api/balance', {
      params: { query: { month: now.getMonth() + 1, year: now.getFullYear() } },
    })
    expect(mockedGet).toHaveBeenCalledWith('/api/analytics/summary', {
      params: { query: { month: now.getMonth() + 1, year: now.getFullYear() } },
    })
  })

  it('shows an empty-categories message when there are no expenses', async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path === '/api/balance') return Promise.resolve({ data: sampleBalance, error: undefined })
      if (path === '/api/analytics/summary')
        return Promise.resolve({ data: { total: 0, count: 0, categories: [] }, error: undefined })
      return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
    })

    renderSidebar()

    expect(await screen.findByText('Нет расходов за этот месяц')).toBeInTheDocument()
  })

  it('flags a shifted payout date with the nominal date', async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path === '/api/balance')
        return Promise.resolve({
          data: { ...sampleBalance, payoutDate1: '2026-08-08', payoutDate1Nominal: '2026-08-10' },
          error: undefined,
        })
      if (path === '/api/analytics/summary')
        return Promise.resolve({ data: sampleAnalytics, error: undefined })
      return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
    })

    renderSidebar()

    const bodyText = (await screen.findByText('К выплате (1-я половина)')).closest('div')
      ?.parentElement?.textContent
    expect(bodyText).toContain('перенесено с')
  })

  it('does not flag a payout date that was not shifted', async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path === '/api/balance') return Promise.resolve({ data: sampleBalance, error: undefined })
      if (path === '/api/analytics/summary')
        return Promise.resolve({ data: sampleAnalytics, error: undefined })
      return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
    })

    renderSidebar()

    await screen.findByText('К выплате (1-я половина)')
    expect(screen.queryByText(/перенесено с/)).not.toBeInTheDocument()
  })

  it('shows the working-days breakdown when that method is active', async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path === '/api/balance')
        return Promise.resolve({
          data: {
            ...sampleBalance,
            calculationMethod: 'working_days',
            workingDaysHalf1: 11,
            workingDaysHalf2: 12,
            workingDaysTotal: 23,
            advanceCutoffDay: 15,
          },
          error: undefined,
        })
      if (path === '/api/analytics/summary')
        return Promise.resolve({ data: sampleAnalytics, error: undefined })
      return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
    })

    renderSidebar()

    expect(await screen.findByText(/Как посчитано/)).toBeInTheDocument()
    expect(screen.getByText(/11 раб\. дней/)).toBeInTheDocument()
  })
})
