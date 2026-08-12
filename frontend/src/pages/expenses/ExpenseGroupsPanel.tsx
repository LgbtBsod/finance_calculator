import { useMemo, useState, type FormEvent } from 'react'
import { Card } from '../../components/ui/Card'
import { Field } from '../../components/ui/Field'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { Spinner } from '../../components/ui/Spinner'
import { useToast } from '../../components/ui/ToastProvider'
import { useConfirm } from '../../components/ui/ConfirmProvider'
import { StickyFormColumn } from '../../components/layout/StickyFormColumn'
import { useUndoableDelete } from '../../hooks/useUndoableDelete'
import {
  useCreateExpenseGroup,
  useDeleteExpenseGroup,
  useExpenseGroups,
  useExpenseItems,
  useUpdateExpenseGroup,
} from '../../hooks/useExpenses'
import { formatCurrency, pluralizeRu } from '../../lib/format'

const DEFAULT_GROUP_COLOR = '#007AFF'

type ExpenseGroupsPanelProps = {
  filterMonth: number
  filterYear: number
  showAllPeriods: boolean
}

/**
 * Группы расходов — вторичное управление относительно самих расходов
 * (см. ExpenseItemsPanel). Выделено из ExpensesPage вместе с ним:
 * раньше форма+список групп и форма+список расходов жили в одном
 * компоненте на 700+ строк с более чем десятком useState.
 *
 * Счётчик расходов у каждой группы считается за тот же период, что
 * выбран в ExpenseItemsPanel (filterMonth/filterYear/showAllPeriods) —
 * поэтому период передаётся сюда пропсами, а не берётся из отдельного
 * запроса "все расходы за всё время".
 */
export function ExpenseGroupsPanel({
  filterMonth,
  filterYear,
  showAllPeriods,
}: ExpenseGroupsPanelProps) {
  const { showToast } = useToast()
  const confirm = useConfirm()

  const [groupName, setGroupName] = useState('')
  const [groupColor, setGroupColor] = useState(DEFAULT_GROUP_COLOR)
  const [groupMonthlyLimit, setGroupMonthlyLimit] = useState('')
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null)
  // Форма создания/редактирования теперь в модалке (см. Modal), а не
  // постоянно видимым блоком над списком — на невысоком экране/окне она
  // одна занимала столько места, что список групп уходил за пределы
  // видимой области и выглядел как "группы пропали", хотя это был просто
  // скролл. Модалка открывается по кнопке "+ Добавить группу" (всегда на
  // виду, в нескроллящейся части колонки) или по "✏️" у карточки группы.
  const [isModalOpen, setIsModalOpen] = useState(false)

  const groupsQuery = useExpenseGroups()
  const itemsQuery = useExpenseItems(
    showAllPeriods ? null : filterMonth,
    showAllPeriods ? null : filterYear,
  )

  const createGroup = useCreateExpenseGroup()
  const updateGroup = useUpdateExpenseGroup()
  const deleteGroup = useDeleteExpenseGroup()
  const groupDeletion = useUndoableDelete<string>()

  const groups = (groupsQuery.data ?? []).filter((group) => !groupDeletion.isPending(group.id))

  const itemCountByGroup = useMemo(() => {
    const counts = new Map<string, number>()
    for (const item of itemsQuery.data ?? []) {
      if (!item.groupId) continue
      counts.set(item.groupId, (counts.get(item.groupId) ?? 0) + 1)
    }
    return counts
  }, [itemsQuery.data])

  function openAddModal() {
    setEditingGroupId(null)
    setGroupName('')
    setGroupColor(DEFAULT_GROUP_COLOR)
    setGroupMonthlyLimit('')
    setIsModalOpen(true)
  }

  function startEditGroup(
    groupId: string,
    name: string,
    color: string,
    monthlyLimit: number | null,
  ) {
    setEditingGroupId(groupId)
    setGroupName(name)
    setGroupColor(color)
    setGroupMonthlyLimit(monthlyLimit != null ? String(monthlyLimit) : '')
    setIsModalOpen(true)
  }

  function cancelEditGroup() {
    setEditingGroupId(null)
    setGroupName('')
    setGroupColor(DEFAULT_GROUP_COLOR)
    setGroupMonthlyLimit('')
    setIsModalOpen(false)
  }

  function handleSubmitGroup(e: FormEvent) {
    e.preventDefault()
    const trimmed = groupName.trim()
    if (!trimmed) return
    const monthlyLimit = groupMonthlyLimit.trim() === '' ? null : Number(groupMonthlyLimit)

    if (editingGroupId) {
      updateGroup.mutate(
        { id: editingGroupId, body: { name: trimmed, color: groupColor, monthlyLimit } },
        {
          onSuccess: () => {
            cancelEditGroup()
            showToast('Группа обновлена', 'success')
          },
          onError: (error) =>
            showToast(
              error instanceof Error ? error.message : 'Не удалось обновить группу',
              'error',
            ),
        },
      )
      return
    }

    createGroup.mutate(
      { name: trimmed, color: groupColor, monthlyLimit },
      {
        onSuccess: () => {
          setGroupName('')
          setGroupMonthlyLimit('')
          setIsModalOpen(false)
          showToast('Группа расходов добавлена', 'success')
        },
        onError: (error) =>
          showToast(error instanceof Error ? error.message : 'Не удалось добавить группу', 'error'),
      },
    )
  }

  async function handleDeleteGroup(groupId: string, name: string) {
    const ok = await confirm({ title: `Удалить группу «${name}»?`, danger: true })
    if (!ok) return
    if (editingGroupId === groupId) cancelEditGroup()
    groupDeletion.scheduleDelete(groupId, `Группа «${name}» удалена`, () => {
      deleteGroup.mutate(groupId, {
        onError: (error) =>
          showToast(error instanceof Error ? error.message : 'Не удалось удалить группу', 'error'),
      })
    })
  }

  const isEditingGroup = editingGroupId !== null

  return (
    <>
      <StickyFormColumn
        form={
          <div className="space-y-4">
            {/* Всегда на виду (нескроллящаяся часть колонки, см. StickyFormColumn) —
              форма создания/редактирования теперь открывается в модалке (ниже),
              а не постоянным блоком: раньше на невысоком окне сама форма
              занимала весь экран и список групп уходил за пределы видимой
              области без скролла, выглядя как "группы пропали". */}
            <Button type="button" variant="primary" className="w-full" onClick={openAddModal}>
              + Добавить группу
            </Button>
          </div>
        }
      >
        <section>
          {groupsQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner /> Загрузка...
            </div>
          )}
          {groupsQuery.isError && (
            <p className="text-danger text-sm">Не удалось загрузить группы расходов</p>
          )}

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
                    interactive
                    style={{ borderLeft: `4px solid ${group.color}` }}
                    className={group.id === editingGroupId ? 'ring-primary/50 ring-2' : undefined}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-base font-semibold" style={{ color: group.color }}>
                          {group.name}
                        </p>
                        <p className="mt-1 text-sm text-gray-500">
                          {count} {pluralizeRu(count, 'расход', 'расхода', 'расходов')}
                          {group.monthlyLimit != null &&
                            ` · лимит ${formatCurrency(group.monthlyLimit)}/мес`}
                        </p>
                      </div>
                      <div className="flex gap-1.5">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          aria-label={`Редактировать группу «${group.name}»`}
                          onClick={() =>
                            startEditGroup(
                              group.id,
                              group.name,
                              group.color,
                              group.monthlyLimit ?? null,
                            )
                          }
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

      <Modal
        open={isModalOpen}
        onClose={cancelEditGroup}
        title={isEditingGroup ? '✏️ Редактирование группы' : '📁 Новая группа расходов'}
      >
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
            <Field label="Месячный лимит, ₽ (необязательно)" htmlFor="group-monthly-limit">
              <Input
                id="group-monthly-limit"
                type="number"
                min={0}
                step="0.01"
                placeholder="Без лимита"
                value={groupMonthlyLimit}
                onChange={(e) => setGroupMonthlyLimit(e.target.value)}
              />
            </Field>
          </div>
          <div className="mt-4 flex gap-3">
            <Button
              type="submit"
              variant="primary"
              disabled={createGroup.isPending || updateGroup.isPending}
            >
              {isEditingGroup ? '💾 Сохранить изменения' : '💾 Сохранить группу'}
            </Button>
            {isEditingGroup && (
              <Button type="button" variant="ghost" onClick={cancelEditGroup}>
                Отмена
              </Button>
            )}
          </div>
        </form>
      </Modal>
    </>
  )
}
