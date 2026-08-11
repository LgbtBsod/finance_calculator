import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from '../components/ui/ToastProvider'
import { ConfirmProvider } from '../components/ui/ConfirmProvider'
import { formatCurrency } from '../lib/format'
import { apiClient } from '../api/client'
import { ExpensesPage } from './ExpensesPage'

vi.mock('../api/client', () => ({
  apiClient: {
    GET: vi.fn(),
    POST: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}))

const mockedGet = apiClient.GET as unknown as ReturnType<typeof vi.fn>
const mockedPost = apiClient.POST as unknown as ReturnType<typeof vi.fn>
const mockedPut = apiClient.PUT as unknown as ReturnType<typeof vi.fn>
const mockedDelete = apiClient.DELETE as unknown as ReturnType<typeof vi.fn>

const groups = [{ id: 'g1', name: 'Продукты', color: '#ff0000', parentId: null, sortOrder: 0 }]

const items = [
  {
    id: 'i1',
    groupId: 'g1',
    name: 'Молоко',
    amount: 150,
    date: '2026-08-01',
    isInclusive: false,
    half: 1,
    isRecurring: false,
    month: 8,
    year: 2026,
  },
]

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <ExpensesPage />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGet.mockImplementation((path: string) => {
    if (path === '/api/expense-groups') return Promise.resolve({ data: groups, error: undefined })
    if (path === '/api/expense-items') return Promise.resolve({ data: items, error: undefined })
    return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
  })
})

describe('ExpensesPage', () => {
  it('renders loaded groups and expense items correctly', async () => {
    renderPage()

    expect(await screen.findByText('Продукты', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getByText('1 расход')).toBeInTheDocument()

    expect(screen.getByText('Молоко')).toBeInTheDocument()
    // formatCurrency uses a non-breaking space between the number and the currency sign;
    // getByText normalizes DOM whitespace to regular spaces, so match with a whitespace-agnostic regex.
    const amountPattern = new RegExp(formatCurrency(150).replace(/\s+/g, '\\s+'))
    expect(screen.getByText(amountPattern)).toBeInTheDocument()
    expect(screen.getByText(/1-я пол\./)).toBeInTheDocument()
  })

  it('submits the new expense form with the correct payload', async () => {
    mockedPost.mockResolvedValue({
      data: { ...items[0], id: 'new-item', name: 'Хлеб', amount: 250 },
      error: undefined,
    })
    const user = userEvent.setup()
    const { container } = renderPage()

    await screen.findByText('Продукты', { selector: 'p' })

    const nameInput = container.querySelector<HTMLInputElement>('#item-name')!
    const amountInput = container.querySelector<HTMLInputElement>('#item-amount')!
    const groupSelect = container.querySelector<HTMLSelectElement>('#item-group')!

    await user.type(nameInput, 'Хлеб')
    await user.clear(amountInput)
    await user.type(amountInput, '250')
    await user.selectOptions(groupSelect, 'g1')

    await user.click(screen.getByRole('button', { name: '+ Добавить расход' }))

    const now = new Date()

    await waitFor(() => {
      expect(mockedPost).toHaveBeenCalledWith('/api/expense-items', {
        body: {
          name: 'Хлеб',
          amount: 250,
          half: 1,
          month: now.getMonth() + 1,
          year: now.getFullYear(),
          isRecurring: false,
          groupId: 'g1',
          recurringUntil: null,
        },
      })
    })
  })

  it('opens the confirm dialog and deletes the expense item on confirmation', async () => {
    mockedDelete.mockResolvedValue({ data: undefined, error: undefined })
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Молоко')

    await user.click(screen.getByRole('button', { name: 'Удалить расход «Молоко»' }))

    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))

    await waitFor(() => {
      expect(mockedDelete).toHaveBeenCalledWith('/api/expense-items/{item_id}', {
        params: { path: { item_id: 'i1' } },
      })
    })
  })

  it('edits an existing group: populates the form, submits PUT, then resets to create mode', async () => {
    mockedPut.mockResolvedValue({
      data: { id: 'g1', name: 'Еда', color: '#00ff00', parentId: null, sortOrder: 0 },
      error: undefined,
    })
    const user = userEvent.setup()
    const { container } = renderPage()

    await screen.findByText('Продукты', { selector: 'p' })

    await user.click(screen.getByRole('button', { name: 'Редактировать группу «Продукты»' }))

    expect(await screen.findByText('✏️ Редактирование группы')).toBeInTheDocument()
    const nameInput = container.querySelector<HTMLInputElement>('#group-name')!
    expect(nameInput.value).toBe('Продукты')

    await user.clear(nameInput)
    await user.type(nameInput, 'Еда')
    await user.click(screen.getByRole('button', { name: '💾 Сохранить изменения' }))

    await waitFor(() => {
      expect(mockedPut).toHaveBeenCalledWith('/api/expense-groups/{group_id}', {
        params: { path: { group_id: 'g1' } },
        body: { name: 'Еда', color: '#ff0000' },
      })
    })

    // Возврат в режим создания после успешного сохранения
    expect(screen.getByText('📁 Новая группа расходов')).toBeInTheDocument()
  })

  it('edits an existing expense item: populates the form and submits PUT with no month/year', async () => {
    mockedPut.mockResolvedValue({ data: items[0], error: undefined })
    const user = userEvent.setup()
    const { container } = renderPage()

    await screen.findByText('Молоко')

    await user.click(screen.getByRole('button', { name: 'Редактировать расход «Молоко»' }))

    expect(await screen.findByText('✏️ Редактирование расхода')).toBeInTheDocument()
    const nameInput = container.querySelector<HTMLInputElement>('#item-name')!
    const amountInput = container.querySelector<HTMLInputElement>('#item-amount')!
    expect(nameInput.value).toBe('Молоко')
    expect(amountInput.value).toBe('150')

    await user.clear(amountInput)
    await user.type(amountInput, '175')
    await user.click(screen.getByRole('button', { name: '💾 Сохранить изменения' }))

    await waitFor(() => {
      expect(mockedPut).toHaveBeenCalledWith('/api/expense-items/{item_id}', {
        params: { path: { item_id: 'i1' } },
        body: {
          name: 'Молоко', amount: 175, half: 1, isRecurring: false,
          groupId: 'g1', recurringUntil: null,
        },
      })
    })

    expect(screen.getByText('💰 Новый расход')).toBeInTheDocument()
  })

  it('shows the recurring-until date field only while "Повторяющийся" is checked, and includes it in the payload', async () => {
    mockedPost.mockResolvedValue({ data: items[0], error: undefined })
    const user = userEvent.setup()
    const { container } = renderPage()

    await screen.findByText('Молоко')

    expect(screen.queryByLabelText(/Завершить повторение/)).not.toBeInTheDocument()

    await user.click(screen.getByLabelText('Повторяющийся расход'))
    const untilInput = await screen.findByLabelText(/Завершить повторение/)

    const nameInput = container.querySelector<HTMLInputElement>('#item-name')!
    const amountInput = container.querySelector<HTMLInputElement>('#item-amount')!
    await user.type(nameInput, 'Кредит')
    await user.clear(amountInput)
    await user.type(amountInput, '5000')
    await user.type(untilInput, '2026-12-31')

    await user.click(screen.getByRole('button', { name: '+ Добавить расход' }))

    await waitFor(() => {
      expect(mockedPost).toHaveBeenCalledWith(
        '/api/expense-items',
        expect.objectContaining({
          body: expect.objectContaining({ isRecurring: true, recurringUntil: '2026-12-31' }),
        }),
      )
    })
  })

  it('cancels editing and restores the create-mode form', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Молоко')
    await user.click(screen.getByRole('button', { name: 'Редактировать расход «Молоко»' }))
    await screen.findByText('✏️ Редактирование расхода')

    await user.click(screen.getByRole('button', { name: 'Отмена' }))

    expect(screen.getByText('💰 Новый расход')).toBeInTheDocument()
    expect(mockedPut).not.toHaveBeenCalled()
  })
})

describe('ExpensesPage filters', () => {
  const filterGroups = [
    { id: 'g1', name: 'Продукты', color: '#ff0000', parentId: null, sortOrder: 0 },
    { id: 'g2', name: 'Транспорт', color: '#00ff00', parentId: null, sortOrder: 1 },
  ]

  const filterItems = [
    {
      id: 'i1', groupId: 'g1', name: 'Молоко', amount: 150, date: '2026-08-01',
      isInclusive: false, half: 1, isRecurring: false, month: 8, year: 2026,
    },
    {
      id: 'i2', groupId: 'g2', name: 'Бензин', amount: 2000, date: '2026-08-01',
      isInclusive: false, half: 2, isRecurring: false, month: 8, year: 2026,
    },
    {
      id: 'i3', groupId: null, name: 'Кредит Т-банк', amount: 5000, date: '2026-08-01',
      isInclusive: false, half: 1, isRecurring: true, recurringUntil: null, month: 8, year: 2026,
    },
  ]

  function renderFilterPage() {
    mockedGet.mockImplementation((path: string) => {
      if (path === '/api/expense-groups') return Promise.resolve({ data: filterGroups, error: undefined })
      if (path === '/api/expense-items') return Promise.resolve({ data: filterItems, error: undefined })
      return Promise.resolve({ data: undefined, error: new Error(`unexpected path ${path}`) })
    })
    return renderPage()
  }

  it('filters by name search (case-insensitive)', async () => {
    const user = userEvent.setup()
    renderFilterPage()
    await screen.findByText('Молоко')

    await user.type(screen.getByLabelText('Поиск'), 'кредит');

    expect(screen.getByText('Кредит Т-банк')).toBeInTheDocument()
    expect(screen.queryByText('Молоко')).not.toBeInTheDocument()
    expect(screen.queryByText('Бензин')).not.toBeInTheDocument()
    expect(screen.getByText('Показано 1 из 3')).toBeInTheDocument()
  })

  it('filters by group, including the "без группы" option', async () => {
    const user = userEvent.setup()
    renderFilterPage()
    await screen.findByText('Молоко')

    await user.selectOptions(screen.getByLabelText('Группа', { selector: '#filter-group' }), '__none__')

    expect(screen.getByText('Кредит Т-банк')).toBeInTheDocument()
    expect(screen.queryByText('Молоко')).not.toBeInTheDocument()
    expect(screen.queryByText('Бензин')).not.toBeInTheDocument()
  })

  it('filters by half of the month', async () => {
    const user = userEvent.setup()
    renderFilterPage()
    await screen.findByText('Молоко')

    await user.selectOptions(screen.getByLabelText('Половина месяца', { selector: '#filter-half' }), '2')

    expect(screen.getByText('Бензин')).toBeInTheDocument()
    expect(screen.queryByText('Молоко')).not.toBeInTheDocument()
    expect(screen.queryByText('Кредит Т-банк')).not.toBeInTheDocument()
  })

  it('filters to recurring-only items', async () => {
    const user = userEvent.setup()
    renderFilterPage()
    await screen.findByText('Молоко')

    await user.click(screen.getByLabelText('Только повторяющиеся'))

    expect(screen.getByText('Кредит Т-банк')).toBeInTheDocument()
    expect(screen.queryByText('Молоко')).not.toBeInTheDocument()
    expect(screen.queryByText('Бензин')).not.toBeInTheDocument()
  })

  it('shows an empty state with a reset link when filters exclude everything, and resets on click', async () => {
    const user = userEvent.setup()
    renderFilterPage()
    await screen.findByText('Молоко')

    await user.type(screen.getByLabelText('Поиск'), 'не существует такого расхода')

    expect(await screen.findByText(/Ничего не найдено по текущим фильтрам/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Сбросить фильтры' }))

    expect(await screen.findByText('Молоко')).toBeInTheDocument()
    expect(screen.getByText('Бензин')).toBeInTheDocument()
    expect(screen.getByText('Кредит Т-банк')).toBeInTheDocument()
  })

  it('combines filters with AND semantics', async () => {
    const user = userEvent.setup()
    renderFilterPage()
    await screen.findByText('Молоко')

    await user.selectOptions(screen.getByLabelText('Группа', { selector: '#filter-group' }), 'g1')
    await user.selectOptions(screen.getByLabelText('Половина месяца', { selector: '#filter-half' }), '2')

    // Молоко — группа g1, но половина 1 (не 2) -> не должно совпасть ни с одним фильтром сразу
    expect(await screen.findByText(/Ничего не найдено по текущим фильтрам/)).toBeInTheDocument()
  })
})
