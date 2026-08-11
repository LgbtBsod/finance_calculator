import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '../components/ui/Button'
import { Card, CardAmount, CardTitle } from '../components/ui/Card'
import { useConfirm } from '../components/ui/ConfirmProvider'
import { StickyFormColumn } from '../components/layout/StickyFormColumn'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import {
  useAutoCreateBirthdayExpenses,
  useBirthdays,
  useCreateBirthday,
  useDeleteBirthday,
  useUpcomingBirthdays,
  useUpdateBirthday,
  type Birthday,
} from '../hooks/useBirthdays'
import {
  buildBirthDateForApi,
  formatBirthDateRu,
  formatCurrency,
  formatDateRu,
  MONTH_NAMES_RU,
  parseBirthDate,
  pluralizeRu,
} from '../lib/format'

const UPCOMING_DAYS = 30
const DAY_OPTIONS = Array.from({ length: 31 }, (_, i) => i + 1)

// День+месяц выбираются из select'ов, а не вводятся текстом — год для ДР
// не имеет значения (BirthdayService считает только день+месяц), поэтому
// его не спрашиваем у пользователя вовсе, см. buildBirthDateForApi.
const birthdaySchema = z.object({
  name: z.string().trim().min(1, 'Введите имя'),
  day: z.string().min(1),
  month: z.string().min(1),
  giftAmount: z.number().min(0, 'Сумма должна быть неотрицательной'),
})

type BirthdayFormValues = z.infer<typeof birthdaySchema>

function defaultFormValues(): BirthdayFormValues {
  return { name: '', day: '1', month: '1', giftAmount: 5000 }
}

function birthdayToFormValues(birthday: Birthday): BirthdayFormValues {
  const parsed = parseBirthDate(birthday.birthDate)
  return {
    name: birthday.name,
    day: String(parsed?.day ?? 1),
    month: String(parsed?.month ?? 1),
    giftAmount: birthday.giftAmount,
  }
}

export function BirthdaysPage() {
  const { data: birthdays, isLoading, isError } = useBirthdays()
  const { data: alerts } = useUpcomingBirthdays(UPCOMING_DAYS)
  const createBirthday = useCreateBirthday()
  const updateBirthday = useUpdateBirthday()
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
    defaultValues: defaultFormValues(),
  })

  // id редактируемой записи — вне формы, по тому же паттерну, что и
  // editingItemId в ExpensesPage.
  const [editingId, setEditingId] = useState<string | null>(null)

  const onSubmit = async (values: BirthdayFormValues) => {
    const birthDate = buildBirthDateForApi(Number(values.day), Number(values.month))
    try {
      if (editingId) {
        await updateBirthday.mutateAsync({
          id: editingId,
          body: { name: values.name, birthDate, giftAmount: values.giftAmount },
        })
        setEditingId(null)
        reset(defaultFormValues())
        showToast('День рождения обновлён', 'success')
        return
      }
      await createBirthday.mutateAsync({ name: values.name, birthDate, giftAmount: values.giftAmount })
      reset(defaultFormValues())
      showToast('День рождения добавлен', 'success')
    } catch {
      showToast(editingId ? 'Не удалось обновить день рождения' : 'Не удалось добавить день рождения', 'error')
    }
  }

  const startEdit = (birthday: Birthday) => {
    setEditingId(birthday.id)
    reset(birthdayToFormValues(birthday))
  }

  const cancelEdit = () => {
    setEditingId(null)
    reset(defaultFormValues())
  }

  const handleDelete = async (id: string, name: string) => {
    const ok = await confirm({ title: `Удалить день рождения «${name}»?`, danger: true })
    if (!ok) return
    if (editingId === id) cancelEdit()
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

  const isEditing = editingId !== null

  return (
    <div className="grid grid-cols-1 gap-8 xl:h-full xl:grid-cols-[1fr_22rem]">
      {/* ЦЕНТР: дни рождения — основной объект этой страницы */}
      <StickyFormColumn
        form={
          <Card variant="default" className="p-5">
            <h2 className="mb-4 text-xl font-semibold">
              {isEditing ? '✏️ Редактирование дня рождения' : '🎂 Новый день рождения'}
            </h2>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <FieldRow>
                <Field label="Имя" htmlFor="birthday-name" error={errors.name?.message}>
                  <Input id="birthday-name" {...register('name')} />
                </Field>
                <Field label="День" htmlFor="birthday-day" error={errors.day?.message}>
                  <Select id="birthday-day" {...register('day')}>
                    {DAY_OPTIONS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Месяц" htmlFor="birthday-month" error={errors.month?.message}>
                  <Select id="birthday-month" {...register('month')}>
                    {MONTH_NAMES_RU.slice(1).map((name, i) => (
                      <option key={name} value={i + 1}>
                        {name}
                      </option>
                    ))}
                  </Select>
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
              <div className="flex gap-3">
                <Button type="submit" disabled={createBirthday.isPending || updateBirthday.isPending}>
                  {isEditing ? '💾 Сохранить изменения' : '+ Добавить день рождения'}
                </Button>
                {isEditing && (
                  <Button type="button" variant="ghost" onClick={cancelEdit}>
                    Отмена
                  </Button>
                )}
              </div>
            </form>
          </Card>
        }
      >
        <section>
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Spinner /> Загрузка...
            </div>
          )}
          {isError && <p className="text-sm text-danger">Не удалось загрузить дни рождения</p>}

          {birthdays && birthdays.length === 0 && (
            <p className="text-sm text-gray-500">🎂 Нет добавленных дней рождения</p>
          )}
          {birthdays && birthdays.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {birthdays.map((birthday) => (
                <Card
                  key={birthday.id}
                  className={birthday.id === editingId ? 'ring-2 ring-primary/50' : undefined}
                >
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle>{birthday.name}</CardTitle>
                    <div className="flex gap-1.5">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Редактировать день рождения «${birthday.name}»`}
                        onClick={() => startEdit(birthday)}
                      >
                        ✏️
                      </Button>
                      <Button
                        type="button"
                        variant="danger"
                        size="sm"
                        aria-label={`Удалить день рождения «${birthday.name}»`}
                        onClick={() => handleDelete(birthday.id, birthday.name)}
                      >
                        🗑️
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm opacity-90">🎂 {formatBirthDateRu(birthday.birthDate)}</p>
                  <CardAmount>{formatCurrency(birthday.giftAmount)}</CardAmount>
                </Card>
              ))}
            </div>
          )}
        </section>
      </StickyFormColumn>

      {/* СПРАВА: напоминания и массовое создание расходов на подарки */}
      <StickyFormColumn
        form={
          <section>
            <h2 className="mb-4 text-xl font-semibold">🔔 Ближайшие напоминания</h2>
            <p className="mb-3 text-xs text-gray-500">За 30 дней до дня рождения</p>
            {alerts && alerts.length > 0 ? (
              <Button
                variant="success"
                className="w-full"
                onClick={handleAutoCreate}
                disabled={autoCreateExpenses.isPending}
              >
                🎁 Создать расходы на подарки за этот месяц
              </Button>
            ) : (
              <p className="text-sm text-gray-500">Нет напоминаний в ближайшие 30 дней</p>
            )}
          </section>
        }
      >
        {alerts && alerts.length > 0 && (
          <div className="space-y-3">
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
          </div>
        )}
      </StickyFormColumn>
    </div>
  )
}
