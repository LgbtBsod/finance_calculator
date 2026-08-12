import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../api/client'
import { ConfirmProvider } from '../components/ui/ConfirmProvider'
import { ToastProvider } from '../components/ui/ToastProvider'
import { formatCurrency } from '../lib/format'
import { DebtsPage } from './DebtsPage'

vi.mock('../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    POST: vi.fn(),
    DELETE: vi.fn(),
  },
}))

const mockedGet = vi.mocked(apiClient.GET)
const mockedPost = vi.mocked(apiClient.POST)
const mockedDelete = vi.mocked(apiClient.DELETE)

/**
 * formatCurrency() inserts non-breaking spaces (Intl.NumberFormat('ru-RU', ...)).
 * getByText() normalizes the DOM node's text (collapsing all whitespace to a
 * regular space) but does not normalize a plain-string matcher, so the
 * expected string needs the same collapsing to compare correctly.
 */
const norm = (s: string) => s.replace(/\s+/g, ' ').trim()

const sampleDebts = [
  {
    id: '1',
    title: 'Кредит на авто',
    totalAmount: 10000,
    repayments: [{ id: 'r1', debtId: '1', amount: 3000, date: '2026-08-01', note: null }],
    createdAt: '2026-08-01T00:00:00',
    month: 8,
    year: 2026,
    // Backend теперь сам считает остаток — раньше DebtsPage пересчитывал
    // то же самое из repayments на клиенте.
    repaidAmount: 3000,
    remainingAmount: 7000,
  },
]

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <DebtsPage />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGet.mockResolvedValue({ data: sampleDebts, error: undefined, response: new Response() })
})

describe('DebtsPage', () => {
  it('renders loaded debts correctly', async () => {
    renderPage()

    expect(await screen.findByText('Кредит на авто')).toBeInTheDocument()
    // remaining/repaid теперь приходят прямо с backend (repaidAmount=3000,
    // remainingAmount=7000 в моке) — фронтенд их больше не пересчитывает.
    expect(screen.getByText(norm(formatCurrency(7000)))).toBeInTheDocument()
    expect(
      screen.getByText(norm(`из ${formatCurrency(10000)} · погашено ${formatCurrency(3000)}`)),
    ).toBeInTheDocument()
    // Сумма самого платежа в списке погашений — отдельный узел от строки "из/погашено" выше.
    expect(screen.getByText(norm(formatCurrency(3000)))).toBeInTheDocument()
  })

  it('submits the debt form and calls the create mutation with the correct payload', async () => {
    mockedPost.mockResolvedValue({
      data: { ...sampleDebts[0], id: '2', title: 'Новый долг', totalAmount: 5000, repayments: [] },
      error: undefined,
      response: new Response(),
    })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Кредит на авто')

    // Форма создания долга теперь в модалке — открывается по кнопке
    // "+ Добавить долг" (см. DebtsPage), а не постоянно видима.
    await user.click(screen.getByRole('button', { name: '+ Добавить долг' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    const now = new Date()
    await user.type(screen.getByLabelText('Название долга'), 'Новый долг')
    await user.type(screen.getByLabelText('Сумма долга'), '5000')
    await user.click(screen.getByRole('button', { name: '💾 Сохранить долг' }))

    await waitFor(() => {
      expect(mockedPost).toHaveBeenCalledWith('/api/debts', {
        body: {
          title: 'Новый долг',
          totalAmount: 5000,
          month: now.getMonth() + 1,
          year: now.getFullYear(),
        },
      })
    })
  })

  it('opens the confirm dialog, hides the debt immediately, and offers "Отменить" instead of deleting right away', async () => {
    // Таймер отмены (useUndoableDelete) и его фактическое срабатывание после
    // 5с проверяются отдельно, на уровне хука (useUndoableDelete.test.ts) —
    // там же под fake-таймерами, без сложного стека QueryClient/ConfirmProvider,
    // с которым react-scheduler под fake-таймерами конфликтует и виснет.
    // Здесь — только то, что видно пользователю немедленно, синхронно.
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Кредит на авто')

    await user.click(screen.getByLabelText('Удалить долг «Кредит на авто»'))
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))

    // Мягкое удаление: карточка прячется сразу же, а не после реального DELETE.
    expect(screen.queryByText('Кредит на авто')).not.toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: 'Отменить' })).toBeInTheDocument()
  })

  it('restores the debt immediately when "Отменить" is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Кредит на авто')
    await user.click(screen.getByLabelText('Удалить долг «Кредит на авто»'))
    await screen.findByRole('alertdialog')
    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))
    expect(screen.queryByText('Кредит на авто')).not.toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Отменить' }))

    expect(await screen.findByText('Кредит на авто')).toBeInTheDocument()
    expect(mockedDelete).not.toHaveBeenCalled()
  })
})
