import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAnalyticsSummary } from '../../hooks/useAnalytics'
import { useBalance } from '../../hooks/useBalance'
import { formatCurrency, formatDateLongRu, MONTH_NAMES_RU } from '../../lib/format'
import { Card, CardAmount, CardTitle } from '../ui/Card'
import { Select } from '../ui/Select'
import { Spinner } from '../ui/Spinner'

const YEAR_RANGE = (() => {
  const current = new Date().getFullYear()
  return Array.from({ length: 4 }, (_, i) => current - 1 + i)
})()

function RemainingLine({ value }: { value: number }) {
  const isDeficit = value < 0
  return (
    <p className="mt-2 text-lg font-bold">
      {isDeficit ? '⚠️ Дефицит ' : 'Остаток '}
      {formatCurrency(Math.abs(value))}
    </p>
  )
}

function PayoutDateLine({ date, nominal }: { date?: string | null; nominal?: string | null }) {
  if (!date) return null
  const wasShifted = nominal && nominal !== date
  return (
    <p className="mt-1.5 text-sm font-medium opacity-95">
      📅 {formatDateLongRu(date)}
      {wasShifted && (
        <span className="block text-xs font-normal opacity-80">
          (перенесено с {formatDateLongRu(nominal)})
        </span>
      )}
    </p>
  )
}

/**
 * Всегда видимая полная сводка баланса + аналитики — заменяет отдельную
 * вкладку "Баланс и ЗП": не нужно переключаться между страницами, чтобы
 * понять "сколько там осталось". Свой выбор периода, независимый от
 * страницы Аналитики.
 */
export function Sidebar() {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())

  const balance = useBalance(month, year)
  const analytics = useAnalyticsSummary(month, year)

  const hasWorkingDaysBreakdown =
    balance.data?.calculationMethod === 'working_days' &&
    typeof balance.data.workingDaysTotal === 'number' &&
    typeof balance.data.workingDaysHalf1 === 'number' &&
    typeof balance.data.workingDaysHalf2 === 'number'

  return (
    <div className="space-y-6">
      <section>
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-xs font-semibold tracking-wide text-gray-500 uppercase">Баланс</span>
        </div>

        <div className="mb-3 flex gap-2">
          <Select
            aria-label="Месяц"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            className="text-sm"
          >
            {MONTH_NAMES_RU.slice(1).map((name, i) => (
              <option key={name} value={i + 1}>
                {name}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Год"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="text-sm"
          >
            {YEAR_RANGE.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </Select>
        </div>

        {balance.isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner /> Загрузка...
          </div>
        )}
        {balance.isError && <p className="text-xs text-danger">Не удалось загрузить баланс</p>}

        {balance.data && (
          <div className="space-y-3">
            <Card className="p-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[11px] text-gray-500">Зарплата</p>
                  <p className="text-sm font-semibold tabular-nums">
                    {formatCurrency(balance.data.netSalary)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-gray-500">Отпускные</p>
                  <p className="text-sm font-semibold tabular-nums">
                    {formatCurrency(balance.data.vacationHalf1 + balance.data.vacationHalf2)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-gray-500">Итого</p>
                  <p className="text-sm font-semibold tabular-nums">
                    {formatCurrency(balance.data.totalAccrued)}
                  </p>
                </div>
              </div>
            </Card>

            <Card variant="success" className="p-4">
              <CardTitle className="mb-1 text-xs">К выплате (1-я половина)</CardTitle>
              <CardAmount className="text-lg">{formatCurrency(balance.data.toPayHalf1)}</CardAmount>
              <PayoutDateLine date={balance.data.payoutDate1} nominal={balance.data.payoutDate1Nominal} />
              <RemainingLine value={balance.data.balanceHalf1} />
            </Card>
            <Card variant="warning" className="p-4">
              <CardTitle className="mb-1 text-xs">К выплате (2-я половина)</CardTitle>
              <CardAmount className="text-lg">{formatCurrency(balance.data.toPayHalf2)}</CardAmount>
              <PayoutDateLine date={balance.data.payoutDate2} nominal={balance.data.payoutDate2Nominal} />
              <RemainingLine value={balance.data.balanceHalf2} />
            </Card>

            {hasWorkingDaysBreakdown && (
              <Card className="p-3 text-xs text-gray-600 dark:text-gray-400">
                <p className="mb-1.5 font-semibold text-gray-700 dark:text-gray-300">
                  📐 Как посчитано (день отсечения — {balance.data.advanceCutoffDay})
                </p>
                <p>
                  1-я половина: {balance.data.workingDaysHalf1} раб. дней · 2-я половина:{' '}
                  {balance.data.workingDaysHalf2} раб. дней · всего {balance.data.workingDaysTotal}
                </p>
              </Card>
            )}
          </div>
        )}
      </section>

      <section>
        <Link
          to="/analytics"
          className="mb-2 block text-xs font-semibold tracking-wide text-gray-500 uppercase hover:text-primary"
        >
          Аналитика
        </Link>

        {analytics.isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner /> Загрузка...
          </div>
        )}
        {analytics.isError && <p className="text-xs text-danger">Не удалось загрузить аналитику</p>}

        {analytics.data && (
          <Card className="p-4">
            <p className="text-xs text-gray-500">Расходы за месяц</p>
            <p className="text-lg font-bold tabular-nums">{formatCurrency(analytics.data.total)}</p>

            {analytics.data.categories.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {analytics.data.categories.slice(0, 5).map((cat) => (
                  <li key={cat.name} className="flex items-center justify-between gap-2 text-xs">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span
                        className="h-2 w-2 flex-none rounded-full"
                        style={{ backgroundColor: cat.color }}
                      />
                      <span className="truncate text-gray-700 dark:text-gray-300">{cat.name}</span>
                    </span>
                    <span className="flex-none font-medium tabular-nums">
                      {formatCurrency(cat.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-gray-500">Нет расходов за этот месяц</p>
            )}
          </Card>
        )}
      </section>
    </div>
  )
}
