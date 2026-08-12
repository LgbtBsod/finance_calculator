import { useMemo, useState } from 'react'
import { formatCurrency, MONTH_NAMES_RU } from '../../lib/format'

export interface TrendMonthCategory {
  groupId?: string | null
  name: string
  color: string
  amount: number
}

export interface TrendMonthData {
  month: number
  year: number
  total: number
  categories: TrendMonthCategory[]
}

interface SpendingTrendChartProps {
  months: TrendMonthData[]
}

const CHART_HEIGHT = 200
const BAR_MAX_WIDTH = 24
const BAND_MIN_WIDTH = 56
const AXIS_LABEL_HEIGHT = 24
const GAP_PX = 2
const NONE_KEY = '__none__'
const NONE_COLOR = '#9ca3af' // тот же серый, что и "Без группы" в /api/analytics/summary

function niceCeil(value: number): number {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const steps = [1, 2, 5, 10]
  for (const step of steps) {
    const candidate = step * magnitude
    if (candidate >= value) return candidate
  }
  return 10 * magnitude
}

/** Скруглённый только сверху прямоугольник — верхний сегмент стека
 * (marks-and-anatomy.md: "4px rounded data-end, square at baseline"). */
function roundedTopRectPath(x: number, y: number, w: number, h: number, r: number): string {
  const radius = Math.min(r, w / 2, h)
  if (radius <= 0) return `M${x},${y} h${w} v${h} h${-w} Z`
  return [
    `M${x},${y + radius}`,
    `a${radius},${radius} 0 0 1 ${radius},${-radius}`,
    `h${w - 2 * radius}`,
    `a${radius},${radius} 0 0 1 ${radius},${radius}`,
    `v${h - radius}`,
    `h${-w}`,
    `Z`,
  ].join(' ')
}

/**
 * Стек-бар "расходы по категориям за N месяцев" — тренд + состав одновременно
 * (part-to-whole по времени, см. dataviz-скилл: "Trend + composition ->
 * stacked bar"). Порядок категорий в стеке — ФИКСИРОВАННЫЙ (по суммарной
 * величине за весь период, "Без группы" всегда последней), одинаковый во
 * всех столбцах: иначе сегменты "прыгали" бы местами между месяцами и
 * ломали бы визуальное сравнение одной и той же категории со временем.
 */
export function SpendingTrendChart({ months }: SpendingTrendChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  const { order, maxTotal } = useMemo(() => {
    const totals = new Map<string, { name: string; color: string; total: number }>()
    for (const m of months) {
      for (const c of m.categories) {
        const key = c.groupId ?? NONE_KEY
        const existing = totals.get(key)
        if (existing) existing.total += c.amount
        else totals.set(key, { name: c.name, color: c.color, total: c.amount })
      }
    }
    const entries = [...totals.entries()]
    entries.sort(([keyA, a], [keyB, b]) => {
      if (keyA === NONE_KEY) return 1
      if (keyB === NONE_KEY) return -1
      return b.total - a.total
    })
    return {
      order: entries.map(([key, v]) => ({ key, name: v.name, color: v.color })),
      maxTotal: niceCeil(Math.max(...months.map((m) => m.total), 1)),
    }
  }, [months])

  const bandWidth = Math.max(BAND_MIN_WIDTH, 320 / Math.max(months.length, 1))
  const chartWidth = bandWidth * months.length
  const barWidth = Math.min(BAR_MAX_WIDTH, bandWidth * 0.5)

  if (months.every((m) => m.total === 0)) {
    return <p className="py-6 text-center text-sm text-gray-500">Нет расходов за этот период</p>
  }

  const hoveredMonth = hovered != null ? months[hovered] : null

  return (
    <div>
      <div className="relative overflow-x-auto">
        <svg
          width={chartWidth}
          height={CHART_HEIGHT + AXIS_LABEL_HEIGHT}
          viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT + AXIS_LABEL_HEIGHT}`}
          role="img"
          aria-label="Расходы по месяцам"
          className="min-w-full"
        >
          {/* Гридлайны — recessive hairline, только 0 и максимум (marks-and-anatomy.md). */}
          {[0, maxTotal].map((tick) => {
            const y = CHART_HEIGHT - (tick / maxTotal) * CHART_HEIGHT
            return (
              <line
                key={tick}
                x1={0}
                y1={y}
                x2={chartWidth}
                y2={y}
                stroke="currentColor"
                className="text-gray-200 dark:text-gray-700"
                strokeWidth={1}
              />
            )
          })}

          {months.map((m, i) => {
            const x = i * bandWidth + (bandWidth - barWidth) / 2
            let cursorY = CHART_HEIGHT
            const nonZero = order.filter(
              (o) => (m.categories.find((c) => (c.groupId ?? NONE_KEY) === o.key)?.amount ?? 0) > 0,
            )
            const lastKey = nonZero.at(-1)?.key

            return (
              <g key={`${m.year}-${m.month}`}>
                {order.map((o) => {
                  const cat = m.categories.find((c) => (c.groupId ?? NONE_KEY) === o.key)
                  const amount = cat?.amount ?? 0
                  if (amount <= 0) return null
                  const rawHeight = (amount / maxTotal) * CHART_HEIGHT
                  const height = Math.max(rawHeight - GAP_PX, 1)
                  const y = cursorY - rawHeight
                  cursorY -= rawHeight
                  const isTop = o.key === lastKey
                  const color = o.key === NONE_KEY ? NONE_COLOR : o.color
                  return isTop ? (
                    <path key={o.key} d={roundedTopRectPath(x, y, barWidth, height, 4)} fill={color} />
                  ) : (
                    <rect key={o.key} x={x} y={y} width={barWidth} height={height} fill={color} />
                  )
                })}
                {/* Прозрачный хит-таргет на всю высоту полосы — курсор не обязан попасть
                    ровно в сегмент, чтобы получить подсказку по всему столбцу (interaction.md). */}
                <rect
                  x={i * bandWidth}
                  y={0}
                  width={bandWidth}
                  height={CHART_HEIGHT}
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(i)}
                  onBlur={() => setHovered(null)}
                  tabIndex={0}
                  role="img"
                  aria-label={`${MONTH_NAMES_RU[m.month]} ${m.year}: ${formatCurrency(m.total)}`}
                />
                <text
                  x={i * bandWidth + bandWidth / 2}
                  y={CHART_HEIGHT + 16}
                  textAnchor="middle"
                  className="fill-gray-500 text-[11px]"
                >
                  {MONTH_NAMES_RU[m.month].slice(0, 3)}
                </text>
              </g>
            )
          })}
        </svg>

        {hoveredMonth && (
          <div
            className="pointer-events-none absolute top-0 z-10 min-w-[160px] rounded-lg border border-gray-200 bg-white p-3 text-sm shadow-lg dark:border-gray-700 dark:bg-gray-800"
            style={{
              left: Math.min(
                hovered! * bandWidth + bandWidth + 8,
                chartWidth - 168,
              ),
            }}
          >
            <p className="mb-1.5 font-semibold text-gray-900 dark:text-gray-100">
              {MONTH_NAMES_RU[hoveredMonth.month]} {hoveredMonth.year}
            </p>
            <ul className="space-y-1">
              {hoveredMonth.categories
                .filter((c) => c.amount > 0)
                .sort((a, b) => b.amount - a.amount)
                .map((c) => (
                  <li key={c.groupId ?? NONE_KEY} className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
                      <span
                        className="h-2 w-2 flex-none rounded-full"
                        style={{ backgroundColor: c.groupId ? c.color : NONE_COLOR }}
                        aria-hidden="true"
                      />
                      {c.name}
                    </span>
                    <span className="font-medium tabular-nums text-gray-900 dark:text-gray-100">
                      {formatCurrency(c.amount)}
                    </span>
                  </li>
                ))}
            </ul>
            <p className="mt-1.5 border-t border-gray-100 pt-1.5 font-semibold text-gray-900 dark:border-gray-700 dark:text-gray-100">
              Итого: {formatCurrency(hoveredMonth.total)}
            </p>
          </div>
        )}
      </div>

      {/* Легенда — фиксированный порядок категорий, тот же, что и в стеке. */}
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-gray-600 dark:text-gray-300">
        {order.map((o) => (
          <li key={o.key} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 flex-none rounded-full"
              style={{ backgroundColor: o.key === NONE_KEY ? NONE_COLOR : o.color }}
              aria-hidden="true"
            />
            {o.name}
          </li>
        ))}
      </ul>
    </div>
  )
}
