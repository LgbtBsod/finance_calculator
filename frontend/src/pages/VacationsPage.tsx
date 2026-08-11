import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import type { components } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardAmount, CardGrid, CardTitle } from '../components/ui/Card'
import { useConfirm } from '../components/ui/ConfirmProvider'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import { useCreateVacation, useDeleteVacation, useVacations } from '../hooks/useVacations'
import { formatCurrency, formatDateRu } from '../lib/format'

type Vacation = components['schemas']['VacationResponse']

const vacationFormSchema = z
  .object({
    totalAmount: z
      .string()
      .min(1, 'Укажите сумму')
      .refine((v) => Number(v) > 0, 'Сумма должна быть больше нуля'),
    payoutDate: z.string().min(1, 'Укажите дату выплаты'),
    startDate: z.string(),
    endDate: z.string(),
  })
  .refine((v) => !v.startDate || !v.endDate || v.startDate <= v.endDate, {
    message: 'Начало отпуска не может быть позже конца',
    path: ['endDate'],
  })

type VacationFormValues = z.infer<typeof vacationFormSchema>

const DEFAULT_VALUES: VacationFormValues = {
  totalAmount: '',
  payoutDate: '',
  startDate: '',
  endDate: '',
}

/** Заголовок карточки: диапазон дат отпуска, если он указан и не сводится к одному дню, иначе дата выплаты. */
function vacationTitle(vacation: Vacation): string {
  if (vacation.startDate !== vacation.endDate) {
    return `${formatDateRu(vacation.startDate)} — ${formatDateRu(vacation.endDate)}`
  }
  return formatDateRu(vacation.payoutDate)
}

export function VacationsPage() {
  const { data, isLoading, isError } = useVacations()
  const createVacation = useCreateVacation()
  const deleteVacation = useDeleteVacation()
  const { showToast } = useToast()
  const confirm = useConfirm()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<VacationFormValues>({
    resolver: zodResolver(vacationFormSchema),
    defaultValues: DEFAULT_VALUES,
  })

  const onSubmit = async (values: VacationFormValues) => {
    try {
      await createVacation.mutateAsync({
        totalAmount: Number(values.totalAmount),
        payoutDate: values.payoutDate,
        startDate: values.startDate ? values.startDate : undefined,
        endDate: values.endDate ? values.endDate : undefined,
      })
      reset(DEFAULT_VALUES)
      showToast('Отпускные добавлены', 'success')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Не удалось добавить отпускные', 'error')
    }
  }

  const handleDelete = async (vacationId: string) => {
    const ok = await confirm({ title: 'Удалить эти отпускные?', danger: true })
    if (!ok) return
    try {
      await deleteVacation.mutateAsync(vacationId)
      showToast('Отпускные удалены', 'success')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Не удалось удалить отпускные', 'error')
    }
  }

  const vacations = [...(data ?? [])].sort((a, b) => a.payoutDate.localeCompare(b.payoutDate))

  return (
    <div className="space-y-8">
      <div>
        <h2 className="mb-4 text-xl font-semibold">Отпускные</h2>
        <p className="text-sm text-gray-500">
          Если указать точный период отпуска (начало и конец), приложение автоматически исключит эти
          дни из расчёта отработанных дней при выборе метода «По рабочим дням» в настройках — дни
          отпуска не считаются рабочими. Дата выплаты определяет, в какую половину месяца добавятся
          сами отпускные.
        </p>
      </div>

      <Card variant="default" className="p-5">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FieldRow>
            <Field label="Сумма отпускных" htmlFor="vacation-amount" error={errors.totalAmount?.message}>
              <Input
                id="vacation-amount"
                type="number"
                min={0}
                step={0.01}
                {...register('totalAmount')}
              />
            </Field>
            <Field
              label="Дата выплаты"
              htmlFor="vacation-payout-date"
              error={errors.payoutDate?.message}
            >
              <Input id="vacation-payout-date" type="date" {...register('payoutDate')} />
            </Field>
          </FieldRow>
          <FieldRow>
            <Field
              label="Начало отпуска (необязательно)"
              htmlFor="vacation-start-date"
              error={errors.startDate?.message}
            >
              <Input id="vacation-start-date" type="date" {...register('startDate')} />
            </Field>
            <Field
              label="Конец отпуска (необязательно)"
              htmlFor="vacation-end-date"
              error={errors.endDate?.message}
            >
              <Input id="vacation-end-date" type="date" {...register('endDate')} />
            </Field>
          </FieldRow>
          <Button type="submit" disabled={createVacation.isPending}>
            + Добавить отпускные
          </Button>
        </form>
      </Card>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Spinner /> Загрузка...
        </div>
      )}
      {isError && <p className="text-sm text-danger">Не удалось загрузить отпускные</p>}

      {data && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">Список отпускных выплат</h2>
          {vacations.length === 0 ? (
            <p className="text-sm text-gray-500">🏖️ Нет отпусных выплат</p>
          ) : (
            <CardGrid>
              {vacations.map((vacation) => (
                <Card key={vacation.id}>
                  <CardTitle>{vacationTitle(vacation)}</CardTitle>
                  <CardAmount>{formatCurrency(vacation.totalAmount)}</CardAmount>
                  <Button
                    variant="danger"
                    size="sm"
                    className="mt-3"
                    onClick={() => handleDelete(vacation.id)}
                  >
                    Удалить
                  </Button>
                </Card>
              ))}
            </CardGrid>
          )}
        </section>
      )}
    </div>
  )
}
