import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '../components/ui/Button'
import { Card, CardAmount, CardGrid, CardTitle } from '../components/ui/Card'
import { useConfirm } from '../components/ui/ConfirmProvider'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import {
  useAutoCreateBirthdayExpenses,
  useBirthdays,
  useCreateBirthday,
  useDeleteBirthday,
  useUpcomingBirthdays,
} from '../hooks/useBirthdays'
import { formatCurrency, formatDateRu, pluralizeRu } from '../lib/format'

const UPCOMING_DAYS = 30

const birthdaySchema = z.object({
  name: z.string().min(1, 'Введите имя'),
  birthDate: z
    .string()
    .regex(/^\d{1,2}\.\d{1,2}\.\d{4}$/, 'Формат: ДД.ММ.ГГГГ'),
  giftAmount: z.number().min(0, 'Сумма должна быть неотрицательной'),
})

type BirthdayFormValues = z.infer<typeof birthdaySchema>

export function BirthdaysPage() {
  const { data: birthdays, isLoading, isError } = useBirthdays()
  const { data: alerts } = useUpcomingBirthdays(UPCOMING_DAYS)
  const createBirthday = useCreateBirthday()
  const deleteBirthday = useDeleteBirthday()
  const autoCreateExpenses = useAutoCreateBirthdayExpenses()
  const confirm = useConfirm()
  const { showToast } = useToast()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BirthdayFormValues>({
    resolver: zodResolver(birthdaySchema),
    defaultValues: { name: '', birthDate: '', giftAmount: 0 },
  })

  const onSubmit = async (values: BirthdayFormValues) => {
    try {
      await createBirthday.mutateAsync(values)
      reset()
      showToast('День рождения добавлен', 'success')
    } catch {
      showToast('Не удалось добавить день рождения', 'error')
    }
  }

  const handleDelete = async (id: string, name: string) => {
    const ok = await confirm({ title: `Удалить день рождения «${name}»?`, danger: true })
    if (!ok) return
    try {
      await deleteBirthday.mutateAsync(id)
      showToast('День рождения удалён', 'success')
    } catch {
      showToast('Не удалось удалить день рождения', 'error')
    }
  }

  const handleAutoCreate = async () => {
    try {
      const result = await autoCreateExpenses.mutateAsync()
      const created = result?.created ?? 0
      if (created > 0) {
        showToast(`Создано расходов: ${created}`, 'success')
      } else {
        showToast('Нет новых расходов для создания', 'info')
      }
    } catch {
      showToast('Не удалось создать расходы на подарки', 'error')
    }
  }

  return (
    <div className="space-y-8">
      <Card variant="default" className="p-5">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FieldRow>
            <Field label="Имя" htmlFor="birthday-name" error={errors.name?.message}>
              <Input id="birthday-name" {...register('name')} />
            </Field>
            <Field
              label="Дата рождения (ДД.ММ.ГГГГ)"
              htmlFor="birthday-date"
              error={errors.birthDate?.message}
            >
              <Input
                id="birthday-date"
                type="text"
                placeholder="15.03.1990"
                {...register('birthDate')}
              />
            </Field>
            <Field label="Сумма подарка" htmlFor="birthday-amount" error={errors.giftAmount?.message}>
              <Input
                id="birthday-amount"
                type="number"
                min={0}
                {...register('giftAmount', { valueAsNumber: true })}
              />
            </Field>
          </FieldRow>
          <Button type="submit" disabled={createBirthday.isPending}>
            + Добавить день рождения
          </Button>
        </form>
      </Card>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Spinner /> Загрузка...
        </div>
      )}
      {isError && <p className="text-sm text-danger">Не удалось загрузить дни рождения</p>}

      {alerts && alerts.length > 0 && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">🔔 Ближайшие напоминания (за 30 дней до ДР)</h2>
          <CardGrid>
            {alerts.map((alert) => (
              <Card key={`${alert.name}-${alert.triggerDate}`} variant="warning">
                <CardTitle>{alert.name}</CardTitle>
                <p className="text-sm opacity-90">
                  Через {alert.daysUntil} {pluralizeRu(alert.daysUntil, 'день', 'дня', 'дней')} (
                  {formatDateRu(alert.triggerDate)})
                </p>
                <CardAmount>{formatCurrency(alert.giftAmount)}</CardAmount>
              </Card>
            ))}
          </CardGrid>
          <Button
            variant="success"
            className="mt-4"
            onClick={handleAutoCreate}
            disabled={autoCreateExpenses.isPending}
          >
            🎁 Создать расходы на подарки за этот месяц
          </Button>
        </section>
      )}

      <section>
        <h2 className="mb-4 text-xl font-semibold">Дни рождения</h2>
        {birthdays && birthdays.length === 0 && (
          <p className="text-sm text-gray-500">🎂 Нет добавленных дней рождения</p>
        )}
        {birthdays && birthdays.length > 0 && (
          <CardGrid>
            {birthdays.map((birthday) => (
              <Card key={birthday.id}>
                <CardTitle>{birthday.name}</CardTitle>
                <p className="text-sm opacity-90">🎂 {birthday.birthDate}</p>
                <CardAmount>{formatCurrency(birthday.giftAmount)}</CardAmount>
                <Button
                  variant="danger"
                  size="sm"
                  className="mt-3"
                  onClick={() => handleDelete(birthday.id, birthday.name)}
                >
                  Удалить
                </Button>
              </Card>
            ))}
          </CardGrid>
        )}
      </section>
    </div>
  )
}
