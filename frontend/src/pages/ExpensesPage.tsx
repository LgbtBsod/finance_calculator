import { useMemo, useState, type FormEvent } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Card } from '../components/ui/Card'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Switch } from '../components/ui/Switch'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import { useConfirm } from '../components/ui/ConfirmProvider'
import { StickyFormColumn } from '../components/layout/StickyFormColumn'
import {
  useCreateExpenseGroup,
  useCreateExpenseItem,
  useDeleteExpenseGroup,
  useDeleteExpenseItem,
  useExpenseGroups,
  useExpenseItems,
  useUpdateExpenseGroup,
  useUpdateExpenseItem,
  type ExpenseItem,
} from '../hooks/useExpenses'
import { formatCurrency, formatDateRu, MONTH_NAMES_RU, pluralizeRu } from '../lib/format'

const DEFAULT_GROUP_COLOR = '#007AFF'

const YEAR_RANGE = (() => {
  const current = new Date().getFullYear()
  return Array.from({ length: 4 }, (_, i) => current - 1 + i)
})()

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

export function ExpensesPage() {
  const now = new Date()
  const { showToast } = useToast()
  const confirm = useConfirm()

  const [groupName, setGroupName] = useState('')
  const [groupColor, setGroupColor] = useState(DEFAULT_GROUP_COLOR)
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null)

  const [editingItemId, setEditingItemId] = useState<string | null>(null)

  const [filterMonth, setFilterMonth] = useState(now.getMonth() + 1)
  const [filterYear, setFilterYear] = useState(now.getFullYear())
  const [showAllPeriods, setShowAllPeriods] = useState(false)

  // Уточняющие фильтры по уже загруженному периоду — чисто клиентские:
  // расходов за период обычно десятки, а не тысячи, гонять их через API
  // ради фильтрации по названию/группе/половине было бы избыточно.
  const [searchQuery, setSearchQuery] = useState('')
  const [filterGroupId, setFilterGroupId] = useState('')
  const [filterHalf, setFilterHalf] = useState<'' | '1' | '2'>('')
  const [recurringOnly, setRecurringOnly] = useState(false)

  const groupsQuery = useExpenseGroups()
  const itemsQuery = useExpenseItems(showAllPeriods ? null : filterMonth, showAllPeriods ? null : filterYear)

  const createGroup = useCreateExpenseGroup()
  const updateGroup = useUpdateExpenseGroup()
  const deleteGroup = useDeleteExpenseGroup()
  const createItem = useCreateExpenseItem()
  const updateItem = useUpdateExpenseItem()
  const deleteItem = useDeleteExpenseItem()

  const groups = groupsQuery.data ?? []
  const items = itemsQuery.data ?? []

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

  const itemCountByGroup = useMemo(() => {
    const counts = new Map<string, number>()
    for (const item of itemsQuery.data ?? []) {
      if (!item.groupId) continue
      counts.set(item.groupId, (counts.get(item.groupId) ?? 0) + 1)
    }
    return counts
  }, [itemsQuery.data])

  const hasActiveFilters =
    searchQuery.trim() !== '' || filterGroupId !== '' || filterHalf !== '' || recurringOnly

  const visibleItems = useMemo(() => {
    const all = itemsQuery.data ?? []
    if (!hasActiveFilters) return all
    const query = searchQuery.trim().toLowerCase()
    return all.filter((item) => {
      if (query && !item.name.toLowerCase().includes(query)) return false
      if (filterGroupId === '__none__' && item.groupId) return false
      if (filterGroupId && filterGroupId !== '__none__' && item.groupId !== filterGroupId) return false
      if (filterHalf && String(item.half) !== filterHalf) return false
      if (recurringOnly && !item.isRecurring) return false
      return true
    })
  }, [itemsQuery.data, hasActiveFilters, searchQuery, filterGroupId, filterHalf, recurringOnly])

  function resetFilters() {
    setSearchQuery('')
    setFilterGroupId('')
    setFilterHalf('')
    setRecurringOnly(false)
  }

  function groupById(groupId: string | null | undefined) {
    return groups.find((g) => g.id === groupId)
  }

  function startEditGroup(groupId: string, name: string, color: string) {
    setEditingGroupId(groupId)
    setGroupName(name)
    setGroupColor(color)
  }

  function cancelEditGroup() {
    setEditingGroupId(null)
    setGroupName('')
    setGroupColor(DEFAULT_GROUP_COLOR)
  }

  function handleSubmitGroup(e: FormEvent) {
    e.preventDefault()
    const trimmed = groupName.trim()
    if (!trimmed) return

    if (editingGroupId) {
      updateGroup.mutate(
        { id: editingGroupId, body: { name: trimmed, color: groupColor } },
        {
          onSuccess: () => {
            cancelEditGroup()
            showToast('Группа обновлена', 'success')
          },
          onError: () => showToast('Не удалось обновить группу', 'error'),
        },
      )
      return
    }

    createGroup.mutate(
      { name: trimmed, color: groupColor },
      {
        onSuccess: () => {
          setGroupName('')
          showToast('Группа расходов добавлена', 'success')
        },
        onError: () => showToast('Не удалось добавить группу', 'error'),
      },
    )
  }

  async function handleDeleteGroup(groupId: string, name: string) {
    const ok = await confirm({ title: `Удалить группу «${name}»?`, danger: true })
    if (!ok) return
    if (editingGroupId === groupId) cancelEditGroup()
    deleteGroup.mutate(groupId, {
      onSuccess: () => showToast('Группа удалена', 'success'),
      onError: () => showToast('Не удалось удалить группу', 'error'),
    })
  }

  function startEditItem(item: ExpenseItem) {
    setEditingItemId(item.id)
    reset(itemToFormValues(item))
  }

  function cancelEditItem() {
    setEditingItemId(null)
    reset(defaultItemValues())
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
          onError: () => showToast('Не удалось обновить расход', 'error'),
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
          showToast('Расход добавлен', 'success')
        },
        onError: () => showToast('Не удалось добавить расход', 'error'),
      },
    )
  }

  async function handleDeleteItem(itemId: string, name: string) {
    const ok = await confirm({ title: `Удалить расход «${name}»?`, danger: true })
    if (!ok) return
    if (editingItemId === itemId) cancelEditItem()
    deleteItem.mutate(itemId, {
      onSuccess: () => showToast('Расход удалён', 'success'),
      onError: () => showToast('Не удалось удалить расход', 'error'),
    })
  }

  const isEditingGroup = editingGroupId !== null
  const isEditingItem = editingItemId !== null

  return (
    <div className="grid grid-cols-1 gap-8 xl:h-full xl:grid-cols-[1fr_22rem]">
      {/* ЦЕНТР: расходы — основной объект этой страницы */}
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
                    onChange={(e) => setFilterMonth(Number(e.target.value))}
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
                    onChange={(e) => setFilterYear(Number(e.target.value))}
                  >
                    {YEAR_RANGE.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </Select>
                </Field>
                <label className="flex items-center gap-2 pb-3 text-sm text-gray-500" htmlFor="show-all-periods">
                  <Switch
                    id="show-all-periods"
                    checked={showAllPeriods}
                    onChange={(e) => setShowAllPeriods(e.target.checked)}
                  />
                  Показать за все периоды
                </label>
              </div>

              <div className="flex flex-wrap items-end gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
                <Field label="Поиск" htmlFor="filter-search" className="min-w-[180px] flex-[2]">
                  <Input
                    id="filter-search"
                    placeholder="Название расхода..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </Field>
                <Field label="Группа" htmlFor="filter-group">
                  <Select
                    id="filter-group"
                    value={filterGroupId}
                    onChange={(e) => setFilterGroupId(e.target.value)}
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
                    value={filterHalf}
                    onChange={(e) => setFilterHalf(e.target.value as '' | '1' | '2')}
                  >
                    <option value="">Любая</option>
                    <option value="1">1-я половина</option>
                    <option value="2">2-я половина</option>
                  </Select>
                </Field>
                <label className="flex items-center gap-2 pb-3 text-sm text-gray-500" htmlFor="filter-recurring-only">
                  <Switch
                    id="filter-recurring-only"
                    checked={recurringOnly}
                    onChange={(e) => setRecurringOnly(e.target.checked)}
                  />
                  Только повторяющиеся
                </label>
                {hasActiveFilters && (
                  <Button type="button" variant="ghost" size="sm" className="pb-3" onClick={resetFilters}>
                    ✕ Сбросить фильтры
                  </Button>
                )}
              </div>
            </Card>

            <section>
              <h2 className="mb-4 text-xl font-semibold">
                {isEditingItem ? '✏️ Редактирование расхода' : '💰 Новый расход'}
              </h2>
              <Card>
                <form onSubmit={handleSubmit(onSubmitItem)}>
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
                    <Field
                      label={isEditingItem ? 'Месяц (нельзя изменить)' : 'Месяц'}
                      htmlFor="item-month"
                    >
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
                  <label className="mt-1 flex items-center gap-2 text-sm text-gray-500" htmlFor="item-recurring">
                    <Switch id="item-recurring" {...register('isRecurring')} />
                    Повторяющийся расход
                  </label>
                  {isRecurringChecked && (
                    <Field
                      label="Завершить повторение (необязательно)"
                      htmlFor="item-recurring-until"
                      className="mb-4 mt-3 max-w-xs"
                    >
                      <Input id="item-recurring-until" type="date" {...register('recurringUntil')} />
                      <p className="mt-1 text-xs text-gray-500">
                        Расход будет автоматически учитываться в каждом месяце до конца указанного —
                        дальше перестанет попадать в баланс. Оставьте пустым, если срок неизвестен.
                      </p>
                    </Field>
                  )}
                  {!isRecurringChecked && <div className="mb-4" />}
                  <div className="flex gap-3">
                    <Button type="submit" variant="success" disabled={createItem.isPending || updateItem.isPending}>
                      {isEditingItem ? '💾 Сохранить изменения' : '+ Добавить расход'}
                    </Button>
                    {isEditingItem && (
                      <Button type="button" variant="ghost" onClick={cancelEditItem}>
                        Отмена
                      </Button>
                    )}
                  </div>
                </form>
              </Card>
            </section>
          </div>
        }
      >
        <section>
          {itemsQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner /> Загрузка...
            </div>
          )}
          {itemsQuery.isError && <p className="text-sm text-danger">Не удалось загрузить расходы</p>}

          {!itemsQuery.isLoading && !itemsQuery.isError && items.length === 0 && (
            <p className="text-sm text-gray-500">💸 Нет расходов за выбранный период</p>
          )}

          {!itemsQuery.isLoading && !itemsQuery.isError && items.length > 0 && visibleItems.length === 0 && (
            <div className="text-sm text-gray-500">
              🔍 Ничего не найдено по текущим фильтрам.{' '}
              <button type="button" className="text-primary hover:underline" onClick={resetFilters}>
                Сбросить фильтры
              </button>
            </div>
          )}

          {hasActiveFilters && visibleItems.length > 0 && (
            <p className="mb-3 text-xs text-gray-500">
              Показано {visibleItems.length} из {items.length}
            </p>
          )}

          {visibleItems.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {visibleItems.map((item) => {
                const group = groupById(item.groupId)
                return (
                  <Card
                    key={item.id}
                    className={item.id === editingItemId ? 'ring-2 ring-primary/50' : undefined}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-base font-semibold">{item.name}</p>
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
                    <p className="mt-1 text-xl font-bold text-danger">{formatCurrency(item.amount)}</p>
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
                        {item.half === 1 ? '1-я пол.' : '2-я пол.'} · {MONTH_NAMES_RU[item.month]} {item.year}
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
          )}
        </section>
      </StickyFormColumn>

      {/* СПРАВА: группы расходов — вторичное управление */}
      <StickyFormColumn
        form={
          <section>
            <h2 className="mb-4 text-xl font-semibold">
              {isEditingGroup ? '✏️ Редактирование группы' : '📁 Новая группа расходов'}
            </h2>
            <Card>
              <form onSubmit={handleSubmitGroup}>
                <div className="space-y-4">
                  <Field label="Название" htmlFor="group-name">
                    <Input
                      id="group-name"
                      placeholder="Продукты, Транспорт..."
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                    />
                  </Field>
                  <Field label="Цвет" htmlFor="group-color">
                    <Input
                      id="group-color"
                      type="color"
                      value={groupColor}
                      onChange={(e) => setGroupColor(e.target.value)}
                    />
                  </Field>
                </div>
                <div className="mt-4 flex gap-3">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={createGroup.isPending || updateGroup.isPending}
                  >
                    {isEditingGroup ? '💾 Сохранить изменения' : '+ Добавить группу'}
                  </Button>
                  {isEditingGroup && (
                    <Button type="button" variant="ghost" onClick={cancelEditGroup}>
                      Отмена
                    </Button>
                  )}
                </div>
              </form>
            </Card>
          </section>
        }
      >
        <section>
          {groupsQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner /> Загрузка...
            </div>
          )}
          {groupsQuery.isError && <p className="text-sm text-danger">Не удалось загрузить группы расходов</p>}

          {!groupsQuery.isLoading && !groupsQuery.isError && groups.length === 0 && (
            <p className="text-sm text-gray-500">📁 Нет групп расходов</p>
          )}

          {groups.length > 0 && (
            <div className="space-y-3">
              {groups.map((group) => {
                const count = itemCountByGroup.get(group.id) ?? 0
                return (
                  <Card
                    key={group.id}
                    style={{ borderLeft: `4px solid ${group.color}` }}
                    className={group.id === editingGroupId ? 'ring-2 ring-primary/50' : undefined}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-base font-semibold" style={{ color: group.color }}>
                          {group.name}
                        </p>
                        <p className="mt-1 text-sm text-gray-500">
                          {count} {pluralizeRu(count, 'расход', 'расхода', 'расходов')}
                        </p>
                      </div>
                      <div className="flex gap-1.5">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          aria-label={`Редактировать группу «${group.name}»`}
                          onClick={() => startEditGroup(group.id, group.name, group.color)}
                        >
                          ✏️
                        </Button>
                        <Button
                          type="button"
                          variant="danger"
                          size="sm"
                          aria-label={`Удалить группу «${group.name}»`}
                          onClick={() => handleDeleteGroup(group.id, group.name)}
                        >
                          🗑️
                        </Button>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </section>
      </StickyFormColumn>
    </div>
  )
}
