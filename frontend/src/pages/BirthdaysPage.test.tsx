import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../api/client'
import { ConfirmProvider } from '../components/ui/ConfirmProvider'
import { ToastProvider } from '../components/ui/ToastProvider'
import { BirthdaysPage } from './BirthdaysPage'

vi.mock('../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    POST: vi.fn(),
    DELETE: vi.fn(),
  },
}))

const mockedApiClient = apiClient as unknown as {
  GET: ReturnType<typeof vi.fn>
  POST: ReturnType<typeof vi.fn>
  DELETE: ReturnType<typeof vi.fn>
}

const sampleBirthdays = [
  { id: '1', name: 'Аня', birthDate: '15.03.1990', giftAmount: 3000 },
  { id: '2', name: 'Борис', birthDate: '01.01.1985', giftAmount: 5000 },
]

function mockGet(birthdays: unknown[] = [], alerts: unknown[] = []) {
  mockedApiClient.GET.mockImplementation((path: string) => {
    if (path === '/api/birthdays') return Promise.resolve({ data: birthdays, error: undefined })
    if (path === '/api/birthdays/upcoming') return Promise.resolve({ data: alerts, error: undefined })
    return Promise.resolve({ data: undefined, error: undefined })
  })
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <BirthdaysPage />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('BirthdaysPage', () => {
  it('renders loaded birthdays', async () => {
    mockGet(sampleBirthdays, [])

    renderPage()

    expect(await screen.findByText('Аня')).toBeInTheDocument()
    expect(screen.getByText('Борис')).toBeInTheDocument()
    expect(screen.getByText('🎂 15.03.1990')).toBeInTheDocument()
    expect(screen.getByText('🎂 01.01.1985')).toBeInTheDocument()
  })

  it('submits the form and calls the create mutation with the correct payload', async () => {
    mockGet([], [])
    mockedApiClient.POST.mockResolvedValue({
      data: { id: '3', name: 'Вика', birthDate: '20.05.2000', giftAmount: 1500 },
      error: undefined,
    })

    renderPage()
    const user = userEvent.setup()

    await screen.findByText('🎂 Нет добавленных дней рождения')

    await user.type(screen.getByLabelText('Имя'), 'Вика')
    await user.type(screen.getByLabelText('Дата рождения (ДД.ММ.ГГГГ)'), '20.05.2000')
    const amountInput = screen.getByLabelText('Сумма подарка')
    await user.clear(amountInput)
    await user.type(amountInput, '1500')

    await user.click(screen.getByRole('button', { name: '+ Добавить день рождения' }))

    await waitFor(() => {
      expect(mockedApiClient.POST).toHaveBeenCalledWith('/api/birthdays', {
        body: { name: 'Вика', birthDate: '20.05.2000', giftAmount: 1500 },
      })
    })
  })

  it('opens the confirm dialog and deletes the birthday on confirmation', async () => {
    mockGet(sampleBirthdays, [])
    mockedApiClient.DELETE.mockResolvedValue({ data: undefined, error: undefined })

    renderPage()
    const user = userEvent.setup()

    await screen.findByText('Аня')

    const deleteButtons = screen.getAllByRole('button', { name: 'Удалить' })
    await user.click(deleteButtons[0])

    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))

    await waitFor(() => {
      expect(mockedApiClient.DELETE).toHaveBeenCalledWith('/api/birthdays/{birthday_id}', {
        params: { path: { birthday_id: '1' } },
      })
    })
  })
})
