import { useState, type FormEvent } from 'react'
import type { components } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardAmount, CardGrid, CardTitle } from '../components/ui/Card'
import { useConfirm } from '../components/ui/ConfirmProvider'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import {
  useAddRepayment,
  useCreateDebt,
  useDebts,
  useDeleteDebt,
  useDeleteRepayment,
} from '../hooks/useDebts'
import { formatCurrency, formatDateRu } from '../lib/format'

type Debt = components['schemas']['DebtResponse']

const DEBT_CARD_STYLE = {
  background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  color: 'white',
} as const

function getRemaining(debt: Debt): number {
  const repaid = debt.repayments.reduce((sum, r) => sum + r.amount, 0)
  return Math.max(0, debt.totalAmount - repaid)
}

interface DebtCardProps {
  debt: Debt
  isAddingRepayment: boolean
  onDeleteDebt: (debt: Debt) => void
  onAddRepayment: (debtId: string, amount: number) => void
  onDeleteRepayment: (repaymentId: string) => void
}

function DebtCard({
  debt,
  isAddingRepayment,
  onDeleteDebt,
  onAddRepayment,
  onDeleteRepayment,
}: DebtCardProps) {
  const { showToast } = useToast()
  const [repaymentAmount, setRepaymentAmount] = useState('')
  const remaining = getRemaining(debt)

  const handleAddRepayment = () => {
    const amount = Number(repaymentAmount)
    if (!repaymentAmount || !(amount > 0)) {
      showToast('Введите сумму платежа больше нуля', 'warning')
      return
    }
    onAddRepayment(debt.id, amount)
    setRepaymentAmount('')
  }

  return (
    <Card variant="default" className="relative border-none" style={DEBT_CARD_STYLE}>
      <button
        type="button"
        onClick={() => onDeleteDebt(debt)}
        className="absolute right-3 top-3 text-white/80 transition-opacity hover:text-white"
        aria-label="Удалить долг"
      >
        ✕
      </button>

      <CardTitle className="pr-6">{debt.title}</CardTitle>

      {remaining > 0 ? (
        <>
          <CardAmount>{formatCurrency(remaining)}</CardAmount>
          <p className="mt-1 text-sm opacity-90">из {formatCurrency(debt.totalAmount)}</p>
        </>
      ) : (
        <CardAmount>✅ Погашено</CardAmount>
      )}

      {debt.repayments.length > 0 && (
        <div className="mt-4 space-y-1.5 border-t border-white/25 pt-3">
          {debt.repayments.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="opacity-90">
                {formatDateRu(r.date)}
                {r.note ? ` · ${r.note}` : ''}
              </span>
              <span className="flex items-center gap-2 font-medium">
                {formatCurrency(r.amount)}
                <button
                  type="button"
                  onClick={() => onDeleteRepayment(r.id)}
                  className="text-white/80 transition-opacity hover:text-white"
                  aria-label="Удалить платёж"
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

  const [title, setTitle] = useState('')
  const [totalAmount, setTotalAmount] = useState('')

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
      showToast('Долг добавлен', 'success')
    } catch {
      showToast('Не удалось добавить долг', 'error')
    }
  }

  const handleDeleteDebt = async (debt: Debt) => {
    const ok = await confirm({ title: `Удалить долг «${debt.title}»?`, danger: true })
    if (!ok) return
    try {
      await deleteDebt.mutateAsync(debt.id)
      showToast('Долг удалён', 'success')
    } catch {
      showToast('Не удалось удалить долг', 'error')
    }
  }

  const handleAddRepayment = async (debtId: string, amount: number) => {
    try {
      await addRepayment.mutateAsync({ debtId, amount })
      showToast('Платёж добавлен', 'success')
    } catch {
      showToast('Не удалось добавить платёж', 'error')
    }
  }

  const handleDeleteRepayment = async (repaymentId: string) => {
    const ok = await confirm({ title: 'Удалить этот платёж?', danger: true })
    if (!ok) return
    try {
      await deleteRepayment.mutateAsync(repaymentId)
      showToast('Платёж удалён', 'success')
    } catch {
      showToast('Не удалось удалить платёж', 'error')
    }
  }

  return (
    <div className="space-y-8">
      <Card variant="default" className="p-5">
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
            + Добавить долг
          </Button>
        </form>
      </Card>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Spinner /> Загрузка...
        </div>
      )}
      {isError && <p className="text-sm text-danger">Не удалось загрузить долги</p>}

      {data && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">Долги</h2>
          {data.length === 0 ? (
            <p className="text-sm text-gray-500">💳 Нет долгов</p>
          ) : (
            <CardGrid>
              {data.map((debt) => (
                <DebtCard
                  key={debt.id}
                  debt={debt}
                  isAddingRepayment={addRepayment.isPending}
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
  )
}
