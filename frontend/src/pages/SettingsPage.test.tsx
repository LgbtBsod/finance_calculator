import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ConfirmProvider } from '../components/ui/ConfirmProvider'
import { ToastProvider } from '../components/ui/ToastProvider'
import { SettingsPage } from './SettingsPage'
import { apiClient } from '../api/client'

vi.mock('../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    PUT: vi.fn(),
  },
}))

const mockSettings = {
  baseSalary: 100000,
  taxRate: 13,
  kef: 1.2,
  advanceCutoffDay: 15,
  isAdvanceDateInclusive: true,
  accountShortened: false,
  standardHours: 40,
  payoutDay1: 10,
  payoutDay2: 25,
  moveWeekendToFriday: false,
  salaryCalculationMethod: 'proportional',
  firstHalfRatio: 0.4,
  secondHalfRatio: 0.6,
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

  function Providers({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <ConfirmProvider>{children}</ConfirmProvider>
        </ToastProvider>
      </QueryClientProvider>
    )
  }

  const utils = render(<SettingsPage />, { wrapper: Providers })
  return { ...utils, invalidateSpy }
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.GET).mockResolvedValue({ data: mockSettings, error: undefined } as never)
    vi.mocked(apiClient.PUT).mockResolvedValue({ data: mockSettings, error: undefined } as never)
  })

  it('renders loaded settings data correctly', async () => {
    renderPage()

    expect(await screen.findByLabelText('Базовая зарплата (₽)')).toHaveValue(100000)
    expect(screen.getByLabelText('Налог (%)')).toHaveValue(13)
    expect(screen.getByLabelText('Коэффициент (КЕФ)')).toHaveValue(1.2)
    expect(screen.getByLabelText('День отсечения аванса')).toHaveValue(15)
    expect(screen.getByLabelText('Стандартные часы')).toHaveValue(40)
    expect(screen.getByLabelText('Первый день выплаты')).toHaveValue(10)
    expect(screen.getByLabelText('Второй день выплаты')).toHaveValue(25)
    expect(screen.getByLabelText('Метод расчета зарплаты')).toHaveValue('proportional')

    // Метод 'proportional' -> поля кастомных пропорций и чекбоксы рабочих дней скрыты
    expect(screen.queryByLabelText('Доля 1-й половины (0–1)')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('День отсечения включён в 1-ю половину')).not.toBeInTheDocument()
  })

  it('reveals custom-ratio fields and working-days checkboxes based on selected method', async () => {
    const user = userEvent.setup()
    renderPage()

    const methodSelect = await screen.findByLabelText('Метод расчета зарплаты')

    await user.selectOptions(methodSelect, 'custom_proportions')
    expect(screen.getByLabelText('Доля 1-й половины (0–1)')).toHaveValue(0.4)
    expect(screen.getByLabelText('Доля 2-й половины (0–1)')).toHaveValue(0.6)

    await user.selectOptions(methodSelect, 'working_days')
    expect(screen.queryByLabelText('Доля 1-й половины (0–1)')).not.toBeInTheDocument()
    expect(screen.getByLabelText('День отсечения включён в 1-ю половину')).toBeChecked()
    expect(screen.getByLabelText('Учитывать сокращённые дни отдельно')).not.toBeChecked()
  })

  it('submits the form calling the update mutation with the current payload, invalidating caches and toasting', async () => {
    const user = userEvent.setup()
    const { invalidateSpy } = renderPage()

    await screen.findByLabelText('Базовая зарплата (₽)')

    await user.click(screen.getByRole('button', { name: /Сохранить настройки/ }))

    await waitFor(() => expect(apiClient.PUT).toHaveBeenCalledTimes(1))
    expect(apiClient.PUT).toHaveBeenCalledWith('/api/settings', {
      body: expect.objectContaining(mockSettings),
    })

    expect(await screen.findByText('Настройки сохранены')).toBeInTheDocument()

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['settings'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['balance'] })
  })
})
