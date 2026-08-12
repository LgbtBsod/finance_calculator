import { useState, type FormEvent } from 'react'
import type { components } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardAmount, CardGrid, CardTitle } from '../components/ui/Card'
import { useConfirm } from '../components/ui/ConfirmProvider'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import { useUndoableDelete } from '../hooks/useUndoableDelete'
import {
  useAddRepayment,
  useCreateDebt,
  useDebts,
  useDeleteDebt,
  useDeleteRepayment,
} from '../hooks/useDebts'
import { projectDebtPayoff, projectPayoffAtRate } from '../lib/debtProjection'
import { formatCurrency, formatDateRu } from '../lib/format'

type Debt = components['schemas']['DebtResponse']

const MONTH_NAMES_GENITIVE_SHORT = [
  'янв',
  'февр',
  'мар',
  'апр',
  'мая',
  'июн',
  'июл',
  'авг',
  'сен',
  'окт',
  'ноя',
  'дек',
]

function formatMonthYear(date: Date): string {
  return `${MONTH_NAMES_GENITIVE_SHORT[date.getMonth()]} ${date.getFullYear()}`
}

/** "При текущем темпе..." + опциональный "что если платить X/мес" калькулятор. */
function PayoffProjection({ debt }: { debt: Debt }) {
  const [hypotheticalRate, setHypotheticalRate] = useState('')

  const projection = projectDebtPayoff(debt.remainingAmount, debt.repayments)
  const hypotheticalDate =
    hypotheticalRate.trim() !== ''
      ? projectPayoffAtRate(debt.remainingAmount, Number(hypotheticalRate))
      : null

  if (debt.repayments.length === 0) {
    return (
      <p className="mt-3 border-t border-white/25 pt-3 text-xs opacity-75">
        Добавьте платёж, чтобы увидеть прогноз погашения.
      </p>
    )
  }

  return (
    <div className="mt-3 space-y-2 border-t border-white/25 pt-3 text-sm">
      {projection.monthsToPayoff != null && projection.projectedDate ? (
        <p className="opacity-90">
          📈 При темпе ~{formatCurrency(projection.avgMonthlyRate)}/мес — закроется к{' '}
          <span className="font-semibold">{formatMonthYear(projection.projectedDate)}</span> (≈
          {projection.monthsToPayoff} мес.)
        </p>
      ) : (
        <p className="opacity-75">Темп погашения пока не определить.</p>
      )}

      <Input
        type="number"
        min={0}
        step="0.01"
        value={hypotheticalRate}
        onChange={(e) => setHypotheticalRate(e.target.value)}
        placeholder="Что если платить, ₽/мес"
        aria-label="Гипотетический платёж в месяц"
      />
      {hypotheticalDate && (
        <p className="opacity-90">
          При {formatCurrency(Number(hypotheticalRate))}/мес — к{' '}
          <span className="font-semibold">{formatMonthYear(hypotheticalDate)}</span>
        </p>
      )}
    </div>
  )
}

interface DebtCardProps {
  debt: Debt
  isAddingRepayment: boolean
  visibleRepayments: Debt['repayments']
  onDeleteDebt: (debt: Debt) => void
  onAddRepayment: (debtId: string, amount: number) => void
  onDeleteRepayment: (debt: Debt, repaymentId: string, amount: number, date: string) => void
}

function DebtCard({
  debt,
  isAddingRepayment,
  visibleRepayments,
  onDeleteDebt,
  onAddRepayment,
  onDeleteRepayment,
}: DebtCardProps) {
  const { showToast } = useToast()
  const [repaymentAmount, setRepaymentAmount] = useState('')
  // Backend теперь сам считает остаток (repaidAmount/remainingAmount) —
  // раньше фронтенд пересчитывал то же самое заново из debt.repayments,
  // и эти два места могли бы разойтись при будущем изменении правил.
  const remaining = debt.remainingAmount

  const handleAddRepayment = () => {
    const amount = Number(repaymentAmount)
    if (!repaymentAmount || !(amount > 0)) {
      showToast('Введите сумму платежа больше нуля', 'warning')
      return
    }
    if (amount > remaining) {
      showToast(`Платёж больше остатка (${formatCurrency(remaining)})`, 'warning')
      return
    }
    onAddRepayment(debt.id, amount)
    setRepaymentAmount('')
  }

  return (
    <Card variant="danger">
      <div className="flex items-start justify-between gap-2">
        <CardTitle>{debt.title}</CardTitle>
        <button
          type="button"
          onClick={() => onDeleteDebt(debt)}
          aria-label={`Удалить долг «${debt.title}»`}
          // Регрессия: раньше был текстом text-white/80 без подложки — на
          // светлой части градиента контраст падал заметно ниже WCAG AA.
          // Тёмный полупрозрачный кружок держит контраст независимо от
          // того, на каком участке градиента оказался.
          className="flex-none rounded-full bg-black/20 p-1.5 text-sm text-white transition-colors hover:bg-black/30 focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:outline-none"
        >
          🗑️
        </button>
      </div>

      {remaining > 0 ? (
        <>
          <CardAmount>{formatCurrency(remaining)}</CardAmount>
          <p className="mt-1 text-sm opacity-90">
            из {formatCurrency(debt.totalAmount)}
            {debt.repaidAmount > 0 && ` · погашено ${formatCurrency(debt.repaidAmount)}`}
          </p>
        </>
      ) : (
        <CardAmount>✅ Погашено</CardAmount>
      )}

      {visibleRepayments.length > 0 && (
        <div className="mt-4 space-y-1.5 border-t border-white/25 pt-3">
          {visibleRepayments.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="opacity-90">
                {formatDateRu(r.date)}
                {r.note ? ` · ${r.note}` : ''}
              </span>
              <span className="flex items-center gap-2 font-medium">
                {formatCurrency(r.amount)}
                <button
                  type="button"
                  onClick={() => onDeleteRepayment(debt, r.id, r.amount, r.date)}
                  aria-label="Удалить платёж"
                  className="flex-none rounded-full bg-black/20 px-1.5 py-0.5 text-xs text-white transition-colors hover:bg-black/30 focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:outline-none"
                >
                  ✕
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      {remaining > 0 && (
        <div className="mt-4 flex items-end gap-2">
          <Input
            type="number"
            min={0}
            max={remaining}
            step="0.01"
            value={repaymentAmount}
            onChange={(e) => setRepaymentAmount(e.target.value)}
            placeholder="Сумма платежа"
            aria-label="Сумма платежа"
          />
          <Button
            type="button"
            size="sm"
            onClick={handleAddRepayment}
            disabled={isAddingRepayment}
            aria-label="Добавить платёж"
          >
            +
          </Button>
        </div>
      )}

      {remaining > 0 && <PayoffProjection debt={debt} />}
    </Card>
  )
}

export function DebtsPage() {
  const { data, isLoading, isError } = useDebts()
  const createDebt = useCreateDebt()
  const deleteDebt = useDeleteDebt()
  const addRepayment = useAddRepayment()
  const deleteRepayment = useDeleteRepayment()
  const confirm = useConfirm()
  const { showToast } = useToast()
  const debtDeletion = useUndoableDelete<string>()
  const repaymentDeletion = useUndoableDelete<string>()

  const [title, setTitle] = useState('')
  const [totalAmount, setTotalAmount] = useState('')
  // Форма создания долга теперь в модалке (см. Modal), а не постоянно
  // видимым блоком над списком — на невысоком экране/окне она одна занимала
  // столько места, что список долгов уходил за пределы видимой области и
  // выглядел как "долги пропали", хотя это был просто скролл. Модалка
  // открывается по кнопке "+ Добавить долг" (всегда на виду). У долгов, в
  // отличие от расходов (см. ExpenseItemsPanel), нет отдельного flow
  // редактирования — только создание, удаление и платежи по карточке.
  const [isModalOpen, setIsModalOpen] = useState(false)

  function openAddModal() {
    setTitle('')
    setTotalAmount('')
    setIsModalOpen(true)
  }

  function closeAddModal() {
    setTitle('')
    setTotalAmount('')
    setIsModalOpen(false)
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const amount = Number(totalAmount)
    if (!title.trim() || !(amount > 0)) {
      showToast('Заполните название и сумму долга', 'warning')
      return
    }
    try {
      await createDebt.mutateAsync({ title: title.trim(), totalAmount: amount })
      setTitle('')
      setTotalAmount('')
      setIsModalOpen(false)
      showToast('Долг добавлен', 'success')
    } catch {
      showToast('Не удалось добавить долг', 'error')
    }
  }

  const handleDeleteDebt = async (debt: Debt) => {
    const ok = await confirm({ title: `Удалить долг «${debt.title}»?`, danger: true })
    if (!ok) return
    debtDeletion.scheduleDelete(debt.id, `Долг «${debt.title}» удалён`, () => {
      deleteDebt.mutate(debt.id, {
        onError: () => showToast('Не удалось удалить долг', 'error'),
      })
    })
  }

  const handleAddRepayment = async (debtId: string, amount: number) => {
    try {
      await addRepayment.mutateAsync({ debtId, amount })
      showToast('Платёж добавлен', 'success')
    } catch {
      showToast('Не удалось добавить платёж', 'error')
    }
  }

  const handleDeleteRepayment = async (
    debt: Debt,
    repaymentId: string,
    amount: number,
    date: string,
  ) => {
    // Детализация в самом диалоге — как для расходов/ДР/долгов; раньше тут
    // был обезличенный "Удалить этот платёж?", не подтверждающий, какой
    // именно платёж (среди нескольких похожих) сейчас удаляется.
    const ok = await confirm({
      title: `Удалить платёж ${formatCurrency(amount)} от ${formatDateRu(date)} по долгу «${debt.title}»?`,
      danger: true,
    })
    if (!ok) return
    repaymentDeletion.scheduleDelete(repaymentId, `Платёж ${formatCurrency(amount)} удалён`, () => {
      deleteRepayment.mutate(repaymentId, {
        onError: () => showToast('Не удалось удалить платёж', 'error'),
      })
    })
  }

  const visibleDebts = data?.filter((debt) => !debtDeletion.isPending(debt.id)) ?? []

  return (
    <>
      <div className="space-y-8">
        {/* Всегда на виду — форма создания долга теперь открывается в
          модалке (ниже), а не постоянным блоком: раньше на невысоком окне
          сама форма занимала весь экран и список долгов уходил за пределы
          видимой области без скролла, выглядя как "долги пропали". */}
        <Button type="button" className="w-full" onClick={openAddModal}>
          + Добавить долг
        </Button>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner /> Загрузка...
          </div>
        )}
        {isError && <p className="text-danger text-sm">Не удалось загрузить долги</p>}

        {data && (
          <section>
            <h2 className="mb-4 text-xl font-semibold">Долги</h2>
            {visibleDebts.length === 0 ? (
              <p className="text-sm text-gray-500">💳 Нет долгов</p>
            ) : (
              <CardGrid>
                {visibleDebts.map((debt) => (
                  <DebtCard
                    key={debt.id}
                    debt={debt}
                    isAddingRepayment={addRepayment.isPending}
                    visibleRepayments={debt.repayments.filter(
                      (r) => !repaymentDeletion.isPending(r.id),
                    )}
                    onDeleteDebt={handleDeleteDebt}
                    onAddRepayment={handleAddRepayment}
                    onDeleteRepayment={handleDeleteRepayment}
                  />
                ))}
              </CardGrid>
            )}
          </section>
        )}
      </div>

      <Modal open={isModalOpen} onClose={closeAddModal} title="💳 Новый долг">
        <form onSubmit={handleSubmit}>
          <FieldRow>
            <Field label="Название долга" htmlFor="debt-title">
              <Input
                id="debt-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Например, кредит"
              />
            </Field>
            <Field label="Сумма долга" htmlFor="debt-amount">
              <Input
                id="debt-amount"
                type="number"
                min={0}
                step="0.01"
                value={totalAmount}
                onChange={(e) => setTotalAmount(e.target.value)}
                placeholder="0"
              />
            </Field>
          </FieldRow>
          <Button type="submit" className="mt-4" disabled={createDebt.isPending}>
            💾 Сохранить долг
          </Button>
        </form>
      </Modal>
    </>
  )
}
