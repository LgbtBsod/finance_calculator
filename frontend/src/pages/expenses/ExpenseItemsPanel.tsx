import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Card, CardAmount, CardTitle } from '../../components/ui/Card'
import { Field, FieldRow } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Switch } from '../../components/ui/Switch'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { useToast } from '../../components/ui/ToastProvider'
import { useConfirm } from '../../components/ui/ConfirmProvider'
import { StickyFormColumn } from '../../components/layout/StickyFormColumn'
import { ApiError } from '../../lib/apiError'
import {
  useCreateExpenseItem,
  useDeleteExpenseItem,
  useExpenseGroups,
  useExpenseItems,
  useUpdateExpenseItem,
  type ExpenseItem,
} from '../../hooks/useExpenses'
import { useExpenseFilters, type ExpenseSortOption } from '../../hooks/useExpenseFilters'
import { useUndoableDelete } from '../../hooks/useUndoableDelete'
import { formatCurrency, formatDateRu, MONTH_NAMES_RU } from '../../lib/format'

const YEAR_RANGE = (() => {
  const current = new Date().getFullYear()
  return Array.from({ length: 4 }, (_, i) => current - 1 + i)
})()

const SORT_OPTIONS: Array<{ value: ExpenseSortOption; label: string }> = [
  { value: 'date-desc', label: 'Сначала новые' },
  { value: 'date-asc', label: 'Сначала старые' },
  { value: 'amount-desc', label: 'Сумма: сначала больше' },
  { value: 'amount-asc', label: 'Сумма: сначала меньше' },
]

// Поля, приходящие из нативных <input>/<select>, всегда строки — валидируем как строки
// и приводим к числам только при отправке, чтобы не ловить рассинхронизацию
// input/output типов zod-resolver'а (coerce/preprocess даёт разные типы на входе и выходе).
const expenseItemSchema = z.object({
  name: z.string().trim().min(1, 'Введите название'),
  amount: z
    .string()
    .min(1, 'Введите сумму')
    .refine((v) => Number(v) > 0, 'Сумма должна быть больше 0'),
  groupId: z.string(),
  half: z.enum(['1', '2']),
  month: z.string().min(1),
  year: z.string().min(1),
  isRecurring: z.boolean(),
  // '' -> бессрочно (см. onSubmitItem). Значимо только при isRecurring=true —
  // повторяющийся расход автоматически "продолжается" на будущие месяцы,
  // пока не наступит месяц recurringUntil (см. database.py get_expenses).
  recurringUntil: z.string(),
})

type ExpenseItemFormValues = z.infer<typeof expenseItemSchema>

function defaultItemValues(): ExpenseItemFormValues {
  const now = new Date()
  return {
    name: '',
    amount: '',
    groupId: '',
    half: '1',
    month: String(now.getMonth() + 1),
    year: String(now.getFullYear()),
    isRecurring: false,
    recurringUntil: '',
  }
}

function itemToFormValues(item: ExpenseItem): ExpenseItemFormValues {
  return {
    name: item.name,
    amount: String(item.amount),
    groupId: item.groupId ?? '',
    half: item.half === 2 ? '2' : '1',
    month: String(item.month),
    year: String(item.year),
    isRecurring: item.isRecurring,
    recurringUntil: item.recurringUntil ?? '',
  }
}

type ExpenseItemsPanelProps = {
  filterMonth: number
  filterYear: number
  showAllPeriods: boolean
  onFilterMonthChange: (month: number) => void
  onFilterYearChange: (year: number) => void
  onShowAllPeriodsChange: (value: boolean) => void
}

/**
 * Расходы — основной объект страницы (форма создания/редактирования +
 * список с фильтрами/сортировкой/пагинацией). Выделено из ExpensesPage
 * вместе с ExpenseGroupsPanel: раньше обе формы и оба списка жили в одном
 * компоненте на 700+ строк с более чем десятком useState.
 *
 * Клавиатурные сокращения (см. audit — features): Ctrl+Enter в любом
 * поле формы отправляет её, "/" вне полей ввода фокусирует поиск.
 */
export function ExpenseItemsPanel({
  filterMonth,
  filterYear,
  showAllPeriods,
  onFilterMonthChange,
  onFilterYearChange,
  onShowAllPeriodsChange,
}: ExpenseItemsPanelProps) {
  const { showToast } = useToast()
  const confirm = useConfirm()
  const searchInputRef = useRef<HTMLInputElement>(null)
  // true только когда разворот доп. фильтров вызван шоткатом "/" — тогда,
  // и только тогда, после разворота нужно перевести фокус в поиск; обычный
  // клик по стрелочке "Доп. фильтры" не должен неожиданно перехватывать фокус.
  const focusSearchOnExpand = useRef(false)

  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  // Форма создания/редактирования теперь в модалке (см. Modal), а не
  // постоянно видимым блоком над списком — на невысоком экране/окне она
  // одна занимала столько места, что список расходов уходил за пределы
  // видимой области и выглядел как "расходы пропали", хотя это был просто
  // скролл. Модалка открывается по кнопке "+ Добавить расход" (всегда на
  // виду, в нескроллящейся части колонки) или по "✏️" у карточки расхода.
  const [isModalOpen, setIsModalOpen] = useState(false)
  // Доп. фильтры (поиск/группа/половина/сортировка/только повторяющиеся)
  // свёрнуты по умолчанию — раньше они всегда занимали место над списком,
  // хотя основной сценарий — просто посмотреть месяц/год. Разворачиваются
  // по стрелке или автоматически, если ими правда пользуются ("/" фокуса
  // поиска, см. ниже, или если фильтр уже активен при повторном рендере).
  const [showExtraFilters, setShowExtraFilters] = useState(false)

  const groupsQuery = useExpenseGroups()
  const itemsQuery = useExpenseItems(
    showAllPeriods ? null : filterMonth,
    showAllPeriods ? null : filterYear,
  )

  const createItem = useCreateExpenseItem()
  const updateItem = useUpdateExpenseItem()
  const deleteItem = useDeleteExpenseItem()
  const itemDeletion = useUndoableDelete<string>()

  const groups = groupsQuery.data ?? []
  const items = itemsQuery.data ?? []
  const visibleItems = items.filter((item) => !itemDeletion.isPending(item.id))

  const filters = useExpenseFilters(visibleItems)

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<ExpenseItemFormValues>({
    resolver: zodResolver(expenseItemSchema),
    defaultValues: defaultItemValues(),
  })

  const isRecurringChecked = watch('isRecurring')

  function groupById(groupId: string | null | undefined) {
    return groups.find((g) => g.id === groupId)
  }

  function openAddModal() {
    setEditingItemId(null)
    reset(defaultItemValues())
    setIsModalOpen(true)
  }

  function startEditItem(item: ExpenseItem) {
    setEditingItemId(item.id)
    reset(itemToFormValues(item))
    setIsModalOpen(true)
  }

  function cancelEditItem() {
    setEditingItemId(null)
    reset(defaultItemValues())
    setIsModalOpen(false)
  }

  function onSubmitItem(values: ExpenseItemFormValues) {
    if (editingItemId) {
      updateItem.mutate(
        {
          id: editingItemId,
          body: {
            name: values.name,
            amount: Number(values.amount),
            half: Number(values.half) as 1 | 2,
            isRecurring: values.isRecurring,
            groupId: values.groupId === '' ? null : values.groupId,
            recurringUntil: values.recurringUntil === '' ? null : values.recurringUntil,
          },
        },
        {
          onSuccess: () => {
            cancelEditItem()
            showToast('Расход обновлён', 'success')
          },
          onError: (error) => {
            // 404 конкретно здесь означает "расход уже удалили — например,
            // в другой открытой вкладке — пока эта форма его редактировала".
            // Раньше форма оставалась открытой на несуществующей записи, и
            // повторное "Сохранить" бесконечно повторяло тот же неинформативный тост.
            if (error instanceof ApiError && error.status === 404) {
              cancelEditItem()
              showToast('Этот расход уже удалён (возможно, в другой вкладке)', 'error')
              return
            }
            showToast(
              error instanceof Error ? error.message : 'Не удалось обновить расход',
              'error',
            )
          },
        },
      )
      return
    }

    createItem.mutate(
      {
        name: values.name,
        amount: Number(values.amount),
        half: Number(values.half) as 1 | 2,
        month: Number(values.month),
        year: Number(values.year),
        isRecurring: values.isRecurring,
        groupId: values.groupId === '' ? null : values.groupId,
        recurringUntil: values.recurringUntil === '' ? null : values.recurringUntil,
      },
      {
        onSuccess: () => {
          reset(defaultItemValues())
          setIsModalOpen(false)
          showToast('Расход добавлен', 'success')
        },
        onError: (error) =>
          showToast(error instanceof Error ? error.message : 'Не удалось добавить расход', 'error'),
      },
    )
  }

  async function handleDeleteItem(itemId: string, name: string) {
    const ok = await confirm({ title: `Удалить расход «${name}»?`, danger: true })
    if (!ok) return
    if (editingItemId === itemId) cancelEditItem()
    itemDeletion.scheduleDelete(itemId, `Расход «${name}» удалён`, () => {
      deleteItem.mutate(itemId, {
        onError: (error) =>
          showToast(error instanceof Error ? error.message : 'Не удалось удалить расход', 'error'),
      })
    })
  }

  // Ctrl+Enter отправляет форму расхода независимо от того, какое именно
  // поле сейчас в фокусе (обычный Enter не сработает, например, в <select>
  // или на переключателе Switch) — навешено на сам <form>, всплытие
  // keydown от любого потомка долетает до него.
  function handleFormKeyDown(e: ReactKeyboardEvent<HTMLFormElement>) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      void handleSubmit(onSubmitItem)()
    }
  }

  // "/" фокусирует поиск — но только когда пользователь не печатает в
  // каком-то другом поле ввода (иначе не даст ввести "/" в название расхода)
  // и когда не открыт модальный диалог подтверждения (ConfirmProvider,
  // role="alertdialog"/aria-modal="true") — иначе "/" при открытом
  // "Удалить расход?" крадёт фокус из диалога в фоновый поиск.
  useEffect(() => {
    function handleGlobalKeyDown(e: KeyboardEvent) {
      if (e.key !== '/') return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      const isEditable =
        tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable
      if (isEditable) return
      if (document.querySelector('[aria-modal="true"]')) return
      e.preventDefault()
      // Если доп. фильтры свёрнуты, поля поиска в DOM нет — сначала
      // разворачиваем блок, фокус переносим отдельным effect'ом ниже
      // (после разворота), а не здесь: сразу после setState поле ещё не
      // отрендерено.
      setShowExtraFilters(true)
      focusSearchOnExpand.current = true
    }
    document.addEventListener('keydown', handleGlobalKeyDown)
    return () => document.removeEventListener('keydown', handleGlobalKeyDown)
  }, [])

  // Фокус в поиск сразу ПОСЛЕ того, как доп. фильтры физически появились
  // в DOM — если сделать это в самом keydown-хендлере выше, ref ещё
  // указывает на предыдущий (закрытый) рендер.
  useEffect(() => {
    if (showExtraFilters && focusSearchOnExpand.current) {
      searchInputRef.current?.focus()
      focusSearchOnExpand.current = false
    }
  }, [showExtraFilters])

  const isEditingItem = editingItemId !== null

  return (
    <>
      <StickyFormColumn
        form={
          <div className="space-y-4">
            <Card className="space-y-4">
              <div className="flex flex-wrap items-end gap-4">
                <Field label="Месяц" htmlFor="filter-month">
                  <Select
                    id="filter-month"
                    value={filterMonth}
                    disabled={showAllPeriods}
                    onChange={(e) => onFilterMonthChange(Number(e.target.value))}
                  >
                    {MONTH_NAMES_RU.slice(1).map((name, i) => (
                      <option key={name} value={i + 1}>
                        {name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Год" htmlFor="filter-year">
                  <Select
                    id="filter-year"
                    value={filterYear}
                    disabled={showAllPeriods}
                    onChange={(e) => onFilterYearChange(Number(e.target.value))}
                  >
                    {YEAR_RANGE.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </Select>
                </Field>
                <label
                  className="flex items-center gap-2 pb-3 text-sm text-gray-500"
                  htmlFor="show-all-periods"
                >
                  <Switch
                    id="show-all-periods"
                    checked={showAllPeriods}
                    onChange={(e) => onShowAllPeriodsChange(e.target.checked)}
                  />
                  Показать за все периоды
                </label>
              </div>

              <div className="border-t border-gray-100 pt-3 dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => setShowExtraFilters((prev) => !prev)}
                  aria-expanded={showExtraFilters}
                  className="flex items-center gap-1.5 text-sm font-medium text-gray-500 transition-colors hover:text-gray-700 dark:hover:text-gray-300"
                >
                  <span
                    className={`transition-transform ${showExtraFilters ? 'rotate-90' : ''}`}
                    aria-hidden="true"
                  >
                    ▸
                  </span>
                  Доп. фильтры
                  {/* Индикатор активных фильтров, пока блок свёрнут — иначе непонятно,
                    почему список сузился, если сам фильтр не на виду. */}
                  {!showExtraFilters && filters.hasActiveFilters && (
                    <span className="bg-primary/10 text-primary rounded-full px-2 py-0.5 text-xs font-semibold">
                      активны
                    </span>
                  )}
                </button>
              </div>

              {showExtraFilters && (
                <div className="flex flex-wrap items-end gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
                  <Field label="Поиск" htmlFor="filter-search" className="min-w-[180px] flex-[2]">
                    <Input
                      id="filter-search"
                      ref={searchInputRef}
                      placeholder="Название расхода... (/ для фокуса)"
                      value={filters.searchQuery}
                      onChange={(e) => filters.setSearchQuery(e.target.value)}
                    />
                  </Field>
                  <Field label="Группа" htmlFor="filter-group">
                    <Select
                      id="filter-group"
                      value={filters.filterGroupId}
                      onChange={(e) => filters.setFilterGroupId(e.target.value)}
                    >
                      <option value="">Все группы</option>
                      <option value="__none__">Без группы</option>
                      {groups.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Половина месяца" htmlFor="filter-half">
                    <Select
                      id="filter-half"
                      value={filters.filterHalf}
                      onChange={(e) => filters.setFilterHalf(e.target.value as '' | '1' | '2')}
                    >
                      <option value="">Любая</option>
                      <option value="1">1-я половина</option>
                      <option value="2">2-я половина</option>
                    </Select>
                  </Field>
                  <Field label="Сортировка" htmlFor="filter-sort">
                    <Select
                      id="filter-sort"
                      value={filters.sortBy}
                      onChange={(e) => filters.setSortBy(e.target.value as ExpenseSortOption)}
                    >
                      {SORT_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <label
                    className="flex items-center gap-2 pb-3 text-sm text-gray-500"
                    htmlFor="filter-recurring-only"
                  >
                    <Switch
                      id="filter-recurring-only"
                      checked={filters.recurringOnly}
                      onChange={(e) => filters.setRecurringOnly(e.target.checked)}
                    />
                    Только повторяющиеся
                  </label>
                  {filters.hasActiveFilters && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="pb-3"
                      onClick={filters.resetFilters}
                    >
                      ✕ Сбросить фильтры
                    </Button>
                  )}
                </div>
              )}
            </Card>

            {/* Всегда на виду (нескроллящаяся часть колонки, см. StickyFormColumn) —
              форма создания/редактирования теперь открывается в модалке (ниже),
              а не постоянным блоком: раньше на невысоком окне сама форма
              занимала весь экран и список расходов уходил за пределы видимой
              области без скролла, выглядя как "расходы пропали". */}
            <Button type="button" variant="success" className="w-full" onClick={openAddModal}>
              + Добавить расход
            </Button>
          </div>
        }
      >
        <section>
          {itemsQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner /> Загрузка...
            </div>
          )}
          {itemsQuery.isError && (
            <p className="text-danger text-sm">Не удалось загрузить расходы</p>
          )}

          {!itemsQuery.isLoading && !itemsQuery.isError && visibleItems.length === 0 && (
            <p className="text-sm text-gray-500">💸 Нет расходов за выбранный период</p>
          )}

          {!itemsQuery.isLoading &&
            !itemsQuery.isError &&
            visibleItems.length > 0 &&
            filters.visibleItems.length === 0 && (
              <div className="text-sm text-gray-500">
                🔍 Ничего не найдено по текущим фильтрам.{' '}
                <button
                  type="button"
                  className="text-primary hover:underline"
                  onClick={filters.resetFilters}
                >
                  Сбросить фильтры
                </button>
              </div>
            )}

          {filters.hasActiveFilters && filters.visibleItems.length > 0 && (
            <p className="mb-3 text-xs text-gray-500">
              Показано {filters.visibleItems.length} из {visibleItems.length}
            </p>
          )}

          {filters.pagedItems.length > 0 && (
            <div className="@container">
              <div className="grid grid-cols-1 gap-4 @sm:grid-cols-2">
                {filters.pagedItems.map((item) => {
                  const group = groupById(item.groupId)
                  return (
                    <Card
                      key={item.id}
                      interactive
                      className={item.id === editingItemId ? 'ring-primary/50 ring-2' : undefined}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle>{item.name}</CardTitle>
                        <div className="flex gap-1.5">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            aria-label={`Редактировать расход «${item.name}»`}
                            onClick={() => startEditItem(item)}
                          >
                            ✏️
                          </Button>
                          <Button
                            type="button"
                            variant="danger"
                            size="sm"
                            aria-label={`Удалить расход «${item.name}»`}
                            onClick={() => handleDeleteItem(item.id, item.name)}
                          >
                            🗑️
                          </Button>
                        </div>
                      </div>
                      <CardAmount className="text-danger">{formatCurrency(item.amount)}</CardAmount>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                        {group ? (
                          <span
                            className="rounded-full px-2 py-0.5 font-medium"
                            style={{ color: group.color, border: `1px solid ${group.color}` }}
                          >
                            {group.name}
                          </span>
                        ) : (
                          <span className="text-gray-500">Без группы</span>
                        )}
                        <span className="text-gray-500">
                          {item.half === 1 ? '1-я пол.' : '2-я пол.'} · {MONTH_NAMES_RU[item.month]}{' '}
                          {item.year}
                        </span>
                        {item.isRecurring && (
                          <span
                            title={
                              item.recurringUntil
                                ? `Повторяется до ${formatDateRu(item.recurringUntil)}`
                                : 'Повторяется бессрочно'
                            }
                          >
                            🔄{item.recurringUntil && ` до ${formatDateRu(item.recurringUntil)}`}
                          </span>
                        )}
                      </div>
                    </Card>
                  )
                })}
              </div>
            </div>
          )}

          {filters.totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-3 text-sm text-gray-500">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={filters.page <= 1}
                onClick={() => filters.setPage(filters.page - 1)}
              >
                ← Назад
              </Button>
              <span>
                Страница {filters.page} из {filters.totalPages}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={filters.page >= filters.totalPages}
                onClick={() => filters.setPage(filters.page + 1)}
              >
                Далее →
              </Button>
            </div>
          )}
        </section>
      </StickyFormColumn>

      <Modal
        open={isModalOpen}
        onClose={cancelEditItem}
        title={isEditingItem ? '✏️ Редактирование расхода' : '💰 Новый расход'}
      >
        <form onSubmit={handleSubmit(onSubmitItem)} onKeyDown={handleFormKeyDown}>
          <FieldRow>
            <Field label="Название" htmlFor="item-name" error={errors.name?.message}>
              <Input id="item-name" placeholder="Продукты, проезд..." {...register('name')} />
            </Field>
            <Field label="Сумма" htmlFor="item-amount" error={errors.amount?.message}>
              <Input id="item-amount" type="number" min={0} step={0.01} {...register('amount')} />
            </Field>
          </FieldRow>
          <FieldRow>
            <Field label="Группа" htmlFor="item-group">
              <Select id="item-group" {...register('groupId')}>
                <option value="">Без группы</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Половина месяца" htmlFor="item-half">
              <Select id="item-half" {...register('half')}>
                <option value="1">1-я половина месяца</option>
                <option value="2">2-я половина месяца</option>
              </Select>
            </Field>
          </FieldRow>
          <FieldRow>
            <Field label={isEditingItem ? 'Месяц (нельзя изменить)' : 'Месяц'} htmlFor="item-month">
              <Select id="item-month" disabled={isEditingItem} {...register('month')}>
                {MONTH_NAMES_RU.slice(1).map((name, i) => (
                  <option key={name} value={String(i + 1)}>
                    {name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={isEditingItem ? 'Год (нельзя изменить)' : 'Год'} htmlFor="item-year">
              <Select id="item-year" disabled={isEditingItem} {...register('year')}>
                {YEAR_RANGE.map((y) => (
                  <option key={y} value={String(y)}>
                    {y}
                  </option>
                ))}
              </Select>
            </Field>
          </FieldRow>
          <label
            className="mt-1 flex items-center gap-2 text-sm text-gray-500"
            htmlFor="item-recurring"
          >
            <Switch id="item-recurring" {...register('isRecurring')} />
            Повторяющийся расход
          </label>
          {isRecurringChecked && (
            <Field
              label="Завершить повторение (необязательно)"
              htmlFor="item-recurring-until"
              className="mt-3 mb-4 max-w-xs"
            >
              <Input id="item-recurring-until" type="date" {...register('recurringUntil')} />
              <p className="mt-1 text-xs text-gray-500">
                Расход будет автоматически учитываться в каждом месяце до конца указанного — дальше
                перестанет попадать в баланс. Оставьте пустым, если срок неизвестен.
              </p>
            </Field>
          )}
          {!isRecurringChecked && <div className="mb-4" />}
          <div className="flex items-center gap-3">
            <Button
              type="submit"
              variant="success"
              disabled={createItem.isPending || updateItem.isPending}
            >
              {isEditingItem ? '💾 Сохранить изменения' : '💾 Сохранить расход'}
            </Button>
            <Button type="button" variant="ghost" onClick={cancelEditItem}>
              Отмена
            </Button>
            <span className="text-xs text-gray-400">Ctrl+Enter — сохранить</span>
          </div>
        </form>
      </Modal>
    </>
  )
}
