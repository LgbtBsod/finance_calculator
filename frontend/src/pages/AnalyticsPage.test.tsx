import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../api/client'
import { ConfirmProvider } from '../components/ui/ConfirmProvider'
import { ToastProvider } from '../components/ui/ToastProvider'
import { formatCurrency } from '../lib/format'
import { AnalyticsPage } from './AnalyticsPage'

vi.mock('../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    POST: vi.fn(),
    DELETE: vi.fn(),
  },
}))

const mockGET = vi.mocked(apiClient.GET)

// formatCurrency() inserts NBSP separators, which trips up RTL's text matcher
// in some environments — comparing raw textContent side-steps that entirely.
const HEADING = '💰 Общие расходы за период'

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <AnalyticsPage />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

const SAMPLE_SUMMARY = {
  total: 45000,
  count: 12,
  categories: [
    { name: 'Еда', amount: 25000, color: '#ff6b6b' },
    { name: 'Транспорт', amount: 20000, color: '#4dabf7' },
  ],
}

// Имена категорий отличаются от SAMPLE_SUMMARY специально — иначе легенда
// SpendingTrendChart дублирует текст "Еда"/"Транспорт" из списка категорий
// на той же странице, и getByText() падает на "нашёл несколько элементов".
const SAMPLE_TREND = {
  months: [
    { month: 6, year: 2026, total: 30000, categories: [{ groupId: null, name: 'Такси', color: '#ff6b6b', amount: 30000 }] },
    { month: 7, year: 2026, total: 45000, categories: [{ groupId: null, name: 'Такси', color: '#ff6b6b', amount: 45000 }] },
  ],
}

// /api/analytics/summary и /api/analytics/trend возвращают разные формы
// данных ({categories: [...]} vs {months: [...]}) — единый mockResolvedValue
// на любой путь подсовывал бы тренд-графику форму summary и ронял её
// (месяцы — не итерируемы).
function mockGetByPath(overrides: Record<string, unknown> = {}) {
  mockGET.mockImplementation(((path: string) => {
    if (path === '/api/analytics/summary') {
      return Promise.resolve({
        data: overrides.summary ?? SAMPLE_SUMMARY,
        error: undefined,
        response: new Response(),
      })
    }
    if (path === '/api/analytics/trend') {
      return Promise.resolve({
        data: overrides.trend ?? SAMPLE_TREND,
        error: undefined,
        response: new Response(),
      })
    }
    return Promise.resolve({
      data: undefined,
      error: { detail: `unexpected path ${path}` },
      response: new Response(),
    })
  }) as unknown as typeof apiClient.GET)
}

describe('AnalyticsPage', () => {
  beforeEach(() => {
    mockGET.mockReset()
  })

  it('renders the loaded summary and category list', async () => {
    mockGetByPath()

    const { container } = renderPage()

    await screen.findByText(HEADING)
    expect(container.textContent).toContain(formatCurrency(45000))
    expect(screen.getByText('12 записей')).toBeInTheDocument()
    expect(screen.getByText('Еда')).toBeInTheDocument()
    expect(screen.getByText('Транспорт')).toBeInTheDocument()
    expect(container.textContent).toContain(formatCurrency(25000))
    expect(container.textContent).toContain(formatCurrency(20000))

    expect(mockGET).toHaveBeenCalledWith('/api/analytics/summary', {
      params: { query: { month: expect.any(Number), year: expect.any(Number) } },
    })
  })

  it('shows the empty state when there are no categories', async () => {
    mockGetByPath({ summary: { total: 0, count: 0, categories: [] } })

    renderPage()

    expect(await screen.findByText('📊 Нет данных для отображения')).toBeInTheDocument()
  })

  it('shows an error message when the request fails', async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: { detail: [{ loc: ['query', 'month'], msg: 'boom', type: 'value_error' }] },
      response: new Response(),
    } as unknown as Awaited<ReturnType<typeof apiClient.GET>>)

    renderPage()

    expect(await screen.findByText('Не удалось загрузить аналитику')).toBeInTheDocument()
  })

  it('refetches with updated query params when the period changes', async () => {
    mockGetByPath()
    const user = userEvent.setup()

    renderPage()
    await screen.findByText(HEADING)
    const callsBeforeChange = mockGET.mock.calls.length

    await user.selectOptions(screen.getByLabelText('Год'), '2027')

    await screen.findByText(HEADING)
    expect(mockGET.mock.calls.length).toBeGreaterThan(callsBeforeChange)
    // Два запроса (summary + trend) уходят на каждую смену периода — берём
    // последний именно к /api/analytics/summary, а не "последний вызов
    // вообще" (им может оказаться trend, с другой формой query-параметров).
    const summaryCalls = mockGET.mock.calls.filter((call) => call[0] === '/api/analytics/summary')
    const lastSummaryCall = summaryCalls[summaryCalls.length - 1]
    expect(lastSummaryCall[1]).toEqual({ params: { query: { month: expect.any(Number), year: 2027 } } })
  })

  it('triggers another fetch when clicking the manual refresh button', async () => {
    mockGetByPath()
    const user = userEvent.setup()

    renderPage()
    await screen.findByText(HEADING)
    const callsBeforeClick = mockGET.mock.calls.length

    await user.click(screen.getByRole('button', { name: '🔄 Обновить данные' }))

    await screen.findByText(HEADING)
    expect(mockGET.mock.calls.length).toBeGreaterThan(callsBeforeClick)
  })
})
