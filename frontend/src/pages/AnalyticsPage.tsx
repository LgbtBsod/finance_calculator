import { useState } from 'react'
import { Button } from '../components/ui/Button'
import { Card, CardAmount, CardTitle } from '../components/ui/Card'
import { Field, FieldRow } from '../components/ui/Field'
import { Select } from '../components/ui/Select'
import { Spinner } from '../components/ui/Spinner'
import { useAnalyticsSummary } from '../hooks/useAnalytics'
import { formatCurrency, MONTH_NAMES_RU, pluralizeRu } from '../lib/format'

const YEAR_RANGE = (() => {
  const current = new Date().getFullYear()
  return Array.from({ length: 4 }, (_, i) => current - 1 + i)
})()

export function AnalyticsPage() {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())

  const { data, isLoading, isError, isFetching, refetch } = useAnalyticsSummary(month, year)

  return (
    <div className="space-y-8">
      <Card variant="default" className="p-5">
        <FieldRow>
          <Field label="Месяц" htmlFor="analytics-month">
            <Select
              id="analytics-month"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {MONTH_NAMES_RU.slice(1).map((name, i) => (
                <option key={name} value={i + 1}>
                  {name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Год" htmlFor="analytics-year">
            <Select
              id="analytics-year"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {YEAR_RANGE.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </Field>
        </FieldRow>
      </Card>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Spinner /> Загрузка...
        </div>
      )}
      {isError && <p className="text-sm text-danger">Не удалось загрузить аналитику</p>}

      {data && (
        <>
          <section>
            <Card variant="accent" className="p-6">
              <CardTitle className="text-base">💰 Общие расходы за период</CardTitle>
              <CardAmount className="text-3xl">{formatCurrency(data.total)}</CardAmount>
              <p className="mt-2.5 text-sm font-medium opacity-90">
                {data.count} {pluralizeRu(data.count, 'запись', 'записи', 'записей')}
              </p>
            </Card>
          </section>

          <section>
            <h2 className="mb-4 text-xl font-semibold">Расходы по категориям</h2>
            <Card>
              {data.categories.length === 0 ? (
                <div className="py-6 text-center">
                  <p className="text-base font-medium">📊 Нет данных для отображения</p>
                  <p className="mt-1 text-sm text-gray-500">
                    Выберите другой период или добавьте расходы.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {data.categories.map((category) => (
                    <div key={category.name} className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <span
                          className="h-3 w-3 flex-none rounded-full"
                          style={{ backgroundColor: category.color }}
                        />
                        <span className="text-sm font-medium">{category.name}</span>
                      </div>
                      <span className="text-sm font-semibold tabular-nums">
                        {formatCurrency(category.amount)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </section>

          <div>
            <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
              🔄 Обновить данные
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
