import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../api/client'
import { ConfirmProvider } from '../components/ui/ConfirmProvider'
import { ToastProvider } from '../components/ui/ToastProvider'
import { formatCurrency, formatDateRu } from '../lib/format'
import { VacationsPage } from './VacationsPage'

vi.mock('../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    POST: vi.fn(),
    DELETE: vi.fn(),
  },
}))

type AnyMock = ReturnType<typeof vi.fn>

const mockedGet = apiClient.GET as unknown as AnyMock
const mockedPost = apiClient.POST as unknown as AnyMock
const mockedDelete = apiClient.DELETE as unknown as AnyMock

const VACATIONS = [
  {
    id: '1',
    totalAmount: 30000,
    payoutDate: '2026-06-10',
    startDate: '2026-06-01',
    endDate: '2026-06-14',
  },
  {
    id: '2',
    totalAmount: 15000,
    payoutDate: '2026-03-25',
    startDate: null,
    endDate: null,
  },
]

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <VacationsPage />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGet.mockResolvedValue({ data: VACATIONS, error: undefined })
  mockedPost.mockResolvedValue({
    data: { id: '3', totalAmount: 20000, payoutDate: '2026-09-10', startDate: null, endDate: null },
    error: undefined,
  })
  mockedDelete.mockResolvedValue({ data: undefined, error: undefined })
})

describe('VacationsPage', () => {
  it('отображает загруженные отпускные', async () => {
    renderPage()

    expect(await screen.findByText('01.06.2026 — 14.06.2026')).toBeInTheDocument()
    expect(screen.getByText('25.03.2026')).toBeInTheDocument()
    expect(screen.getByText(/30\s?000/)).toBeInTheDocument()
    expect(screen.getByText(/15\s?000/)).toBeInTheDocument()
  })

  it('отправляет форму с правильными данными', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('01.06.2026 — 14.06.2026')

    await user.type(screen.getByLabelText('Сумма отпускных'), '20000')
    fireEvent.change(screen.getByLabelText('Дата выплаты'), { target: { value: '2026-09-10' } })
    fireEvent.change(screen.getByLabelText('Начало отпуска (необязательно)'), {
      target: { value: '2026-09-01' },
    })
    fireEvent.change(screen.getByLabelText('Конец отпуска (необязательно)'), {
      target: { value: '2026-09-05' },
    })

    await user.click(screen.getByRole('button', { name: '+ Добавить отпускные' }))

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith('/api/vacations', {
        body: {
          totalAmount: 20000,
          payoutDate: '2026-09-10',
          startDate: '2026-09-01',
          endDate: '2026-09-05',
        },
      }),
    )
  })

  it('открывает диалог подтверждения, скрывает отпускные немедленно и предлагает "Отменить" вместо немедленного удаления', async () => {
    // Таймер отмены (useUndoableDelete) и его фактическое срабатывание после
    // 5с проверяются отдельно, на уровне хука (useUndoableDelete.test.ts) —
    // там же под fake-таймерами, без сложного стека QueryClient/ConfirmProvider,
    // с которым react-scheduler под fake-таймерами конфликтует и виснет.
    // Здесь — только то, что видно пользователю немедленно, синхронно.
    const user = userEvent.setup()
    renderPage()

    const title = await screen.findByText('01.06.2026 — 14.06.2026')
    const card = title.closest('div') as HTMLElement

    // formatCurrency() вставляет неразрывные пробелы (Intl.NumberFormat) —
    // строим ожидаемый текст той же функцией, а не переписываем его вручную
    // обычными пробелами, иначе acessible-name не совпадёт побайтово.
    const expectedLabel = `Удалить отпускные ${formatCurrency(30000)} от ${formatDateRu('2026-06-10')}`

    await user.click(within(card).getByRole('button', { name: expectedLabel }))

    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'Подтвердить' }))

    // Мягкое удаление: карточка прячется сразу же, а не после реального DELETE.
    expect(screen.queryByText('01.06.2026 — 14.06.2026')).not.toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: 'Отменить' })).toBeInTheDocument()
  })

  it('восстанавливает отпускные немедленно при нажатии "Отменить"', async () => {
    const user = userEvent.setup()
    renderPage()

    const title = await screen.findByText('01.06.2026 — 14.06.2026')
    const card = title.closest('div') as HTMLElement
    const expectedLabel = `Удалить отпускные ${formatCurrency(30000)} от ${formatDateRu('2026-06-10')}`

    await user.click(within(card).getByRole('button', { name: expectedLabel }))
    const dialog = await screen.findByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Подтвердить' }))
    expect(screen.queryByText('01.06.2026 — 14.06.2026')).not.toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Отменить' }))

    expect(await screen.findByText('01.06.2026 — 14.06.2026')).toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()
  })
})
