import { useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Field, FieldRow } from '../components/ui/Field'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Switch } from '../components/ui/Switch'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/ToastProvider'
import { useSettings, useUpdateSettings } from '../hooks/useSettings'

const settingsSchema = z.object({
  baseSalary: z.coerce.number().positive('Должно быть больше 0'),
  taxRate: z.coerce.number().min(0, 'Не может быть отрицательным').max(100, 'Не более 100%'),
  kef: z.coerce.number().positive('Должно быть больше 0'),
  advanceCutoffDay: z.coerce
    .number()
    .int('Целое число')
    .min(1, 'От 1 до 31')
    .max(31, 'От 1 до 31'),
  standardHours: z.coerce.number().positive('Должно быть больше 0'),
  salaryCalculationMethod: z.enum(['proportional', 'custom_proportions', 'working_days']),
  isAdvanceDateInclusive: z.boolean(),
  accountShortened: z.boolean(),
  firstHalfRatio: z.coerce.number().min(0, 'От 0 до 1').max(1, 'От 0 до 1'),
  secondHalfRatio: z.coerce.number().min(0, 'От 0 до 1').max(1, 'От 0 до 1'),
  payoutDay1: z.coerce.number().int('Целое число').min(1, 'От 1 до 31').max(31, 'От 1 до 31'),
  payoutDay2: z.coerce.number().int('Целое число').min(1, 'От 1 до 31').max(31, 'От 1 до 31'),
  moveWeekendToFriday: z.boolean(),
})

// z.coerce.number() делает входной тип (до валидации) отличным от выходного
// (после коэрсии в number) — учитываем это через input/output-типы zod,
// иначе zodResolver не типизируется корректно относительно useForm.
type SettingsFormInput = z.input<typeof settingsSchema>
type SettingsFormValues = z.output<typeof settingsSchema>

const METHOD_OPTIONS: Array<{ value: SettingsFormValues['salaryCalculationMethod']; label: string }> = [
  { value: 'proportional', label: 'Пропорциональный (40%/60%)' },
  { value: 'custom_proportions', label: 'Свои пропорции' },
  { value: 'working_days', label: 'По рабочим дням' },
]

export function SettingsPage() {
  const { data, isLoading, isError } = useSettings()
  const updateMutation = useUpdateSettings()
  const { showToast } = useToast()

  const form = useForm<SettingsFormInput, unknown, SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
  })

  useEffect(() => {
    if (data) {
      form.reset(data as SettingsFormInput)
    }
  }, [data, form])

  const method = form.watch('salaryCalculationMethod')
  const errors = form.formState.errors

  const onSubmit = (values: SettingsFormValues) => {
    updateMutation.mutate(values, {
      onSuccess: () => showToast('Настройки сохранены', 'success'),
      onError: (error) =>
        showToast(error instanceof Error ? error.message : 'Не удалось сохранить настройки', 'error'),
    })
  }

  return (
    <div className="space-y-8">
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Spinner /> Загрузка...
        </div>
      )}
      {isError && <p className="text-sm text-danger">Не удалось загрузить настройки</p>}

      {data && (
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <section>
            <h2 className="mb-4 text-xl font-semibold">Настройки зарплаты</h2>
            <Card variant="default" className="space-y-4 p-5">
              <Field label="Базовая зарплата (₽)" htmlFor="baseSalary" error={errors.baseSalary?.message}>
                <Input id="baseSalary" type="number" step="0.01" {...form.register('baseSalary')} />
              </Field>
              <Field label="Налог (%)" htmlFor="taxRate" error={errors.taxRate?.message}>
                <Input id="taxRate" type="number" step="0.01" {...form.register('taxRate')} />
              </Field>
              <Field label="Коэффициент (КЕФ)" htmlFor="kef" error={errors.kef?.message}>
                <Input id="kef" type="number" step="0.01" {...form.register('kef')} />
              </Field>

              <FieldRow>
                <Field
                  label="День отсечения аванса"
                  htmlFor="advanceCutoffDay"
                  error={errors.advanceCutoffDay?.message}
                >
                  <Input
                    id="advanceCutoffDay"
                    type="number"
                    min={1}
                    max={31}
                    {...form.register('advanceCutoffDay')}
                  />
                </Field>
                <Field label="Стандартные часы" htmlFor="standardHours" error={errors.standardHours?.message}>
                  <Input id="standardHours" type="number" {...form.register('standardHours')} />
                </Field>
              </FieldRow>

              <Field label="Метод расчета зарплаты" htmlFor="salaryCalculationMethod">
                <Select id="salaryCalculationMethod" {...form.register('salaryCalculationMethod')}>
                  {METHOD_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </Field>

              {method === 'custom_proportions' && (
                <FieldRow>
                  <Field
                    label="Доля 1-й половины (0–1)"
                    htmlFor="firstHalfRatio"
                    error={errors.firstHalfRatio?.message}
                  >
                    <Input
                      id="firstHalfRatio"
                      type="number"
                      step={0.05}
                      min={0}
                      max={1}
                      {...form.register('firstHalfRatio')}
                    />
                  </Field>
                  <Field
                    label="Доля 2-й половины (0–1)"
                    htmlFor="secondHalfRatio"
                    error={errors.secondHalfRatio?.message}
                  >
                    <Input
                      id="secondHalfRatio"
                      type="number"
                      step={0.05}
                      min={0}
                      max={1}
                      {...form.register('secondHalfRatio')}
                    />
                  </Field>
                </FieldRow>
              )}

              {method === 'working_days' && (
                <div className="space-y-3">
                  <label htmlFor="isAdvanceDateInclusive" className="flex items-center gap-2 text-sm">
                    <Switch
                      id="isAdvanceDateInclusive"
                      {...form.register('isAdvanceDateInclusive')}
                    />
                    День отсечения включён в 1-ю половину
                  </label>
                  <label htmlFor="accountShortened" className="flex items-center gap-2 text-sm">
                    <Switch id="accountShortened" {...form.register('accountShortened')} />
                    Учитывать сокращённые дни отдельно
                  </label>
                </div>
              )}

              <hr className="my-2 border-gray-200 dark:border-gray-700" />
              <h3 className="text-lg font-semibold">Дни выплаты зарплаты</h3>

              <FieldRow>
                <Field label="Первый день выплаты" htmlFor="payoutDay1" error={errors.payoutDay1?.message}>
                  <Input id="payoutDay1" type="number" min={1} max={31} {...form.register('payoutDay1')} />
                </Field>
                <Field label="Второй день выплаты" htmlFor="payoutDay2" error={errors.payoutDay2?.message}>
                  <Input id="payoutDay2" type="number" min={1} max={31} {...form.register('payoutDay2')} />
                </Field>
              </FieldRow>

              <label htmlFor="moveWeekendToFriday" className="flex items-center gap-2 text-sm">
                <Switch id="moveWeekendToFriday" {...form.register('moveWeekendToFriday')} />
                Переносить выходные дни выплат на пятницу
              </label>

              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? <Spinner /> : '💾'} Сохранить настройки
              </Button>
            </Card>
          </section>
        </form>
      )}

      <section>
        <h2 className="mb-4 text-xl font-semibold">Резервное копирование</h2>
        <Card variant="default" className="space-y-3 p-5">
          <p className="text-sm text-gray-500">
            Все расходы, долги, дни рождения и отпускные хранятся в одном файле на этом
            компьютере — без отдельной копии их можно потерять при сбое диска. Скачайте копию
            и сохраните её отдельно (облако, флешка) на случай, если что-то случится с этим
            компьютером.
          </p>
          {/* Обычная ссылка на GET-эндпоинт, а не fetch+blob в JS — ответ уже
              приходит с Content-Disposition: attachment, браузер сохранит файл сам. */}
          <a
            href="/api/backup"
            download
            className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-5 py-3 text-[15px] font-semibold text-white transition-transform hover:bg-primary-hover active:scale-[0.97] focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/40"
          >
            ⬇️ Скачать резервную копию
          </a>
        </Card>
      </section>
    </div>
  )
}
