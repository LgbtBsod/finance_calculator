import { useId, useState } from 'react'
import { formatCurrency } from '../../lib/format'

export interface DonutCategory {
  name: string
  color: string
  amount: number
}

interface CategoryDonutChartProps {
  categories: DonutCategory[]
  total: number
  /** Скрыть встроенную легенду — когда рядом уже есть свой список категорий
   * (см. AnalyticsPage: он показывает то же самое + лимиты, легенда доната
   * там была бы чистым дублированием). */
  showLegend?: boolean
}

const SIZE = 200
const CENTER = SIZE / 2
const RADIUS = 80
const STROKE = 30
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
// Surface-цвет зазора между секторами — CSS-переменная, а не хардкод, чтобы
// в тёмной теме зазор оставался цветом карточки, а не белой полосой (см.
// marks-and-anatomy.md: "surface gap", а не обводка вокруг сектора).
const GAP_PX = 3

/**
 * Донат-диаграмма "расходы по категориям за месяц" — part-to-whole на одну
 * дату. Цвет секторов — это ЖЕ group.color, что уже используется везде
 * в приложении (бейджи расходов, левая рамка карточки группы), а не новая
 * категориальная палитра: одна и та же группа должна оставаться одного
 * цвета везде, где она отображается.
 */
export function CategoryDonutChart({ categories, total, showLegend = true }: CategoryDonutChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)
  const gradientIdBase = useId()

  const withPct = categories
    .filter((c) => c.amount > 0)
    .map((c) => ({ ...c, pct: total > 0 ? c.amount / total : 0 }))

  // reduce, а не map + внешний "let cumulative" — react-hooks/immutability не
  // разрешает мутировать переменную, захваченную замыканием, между итерациями
  // в теле рендера (некорректно для мемоизации React Compiler).
  const { segments } = withPct.reduce<{
    cumulative: number
    segments: Array<(typeof withPct)[number] & { sliceLength: number; offset: number; index: number }>
  }>(
    (state, c, i) => {
      const sliceLength = Math.max(c.pct * CIRCUMFERENCE - GAP_PX, 0)
      const offset = -(state.cumulative * CIRCUMFERENCE) - GAP_PX / 2
      return {
        cumulative: state.cumulative + c.pct,
        segments: [...state.segments, { ...c, sliceLength, offset, index: i }],
      }
    },
    { cumulative: 0, segments: [] },
  )

  const activeCategory = hovered != null ? segments[hovered] : null

  if (withPct.length === 0) {
    return <p className="py-6 text-center text-sm text-gray-500">Нет расходов за период</p>
  }

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start sm:gap-6">
      <div className="relative flex-none">
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={`Расходы по категориям, всего ${formatCurrency(total)}`}
        >
          <g transform={`rotate(-90 ${CENTER} ${CENTER})`}>
            {/* Фоновое кольцо — трек, на случай если сумма секторов не покрывает 100% из-за GAP_PX. */}
            <circle
              cx={CENTER}
              cy={CENTER}
              r={RADIUS}
              fill="none"
              stroke="currentColor"
              className="text-gray-100 dark:text-gray-700"
              strokeWidth={STROKE}
            />
            {segments.map((seg) => (
              <circle
                key={`${gradientIdBase}-${seg.index}`}
                cx={CENTER}
                cy={CENTER}
                r={RADIUS}
                fill="none"
                stroke={seg.color}
                strokeWidth={STROKE}
                strokeDasharray={`${seg.sliceLength} ${CIRCUMFERENCE - seg.sliceLength}`}
                strokeDashoffset={seg.offset}
                opacity={hovered == null || hovered === seg.index ? 1 : 0.35}
                className="cursor-pointer transition-opacity"
                onMouseEnter={() => setHovered(seg.index)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(seg.index)}
                onBlur={() => setHovered(null)}
                tabIndex={0}
                role="img"
                aria-label={`${seg.name}: ${formatCurrency(seg.amount)} (${Math.round(seg.pct * 100)}%)`}
              />
            ))}
          </g>
        </svg>
        {/* Центр кольца — итог по умолчанию, детали наведённой категории при hover/focus.
            Это не единственный способ узнать значение (см. легенду ниже) — подсказка
            дополняет, а не закрывает доступ к данным (interaction.md). */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          {activeCategory ? (
            <>
              <span className="text-xs text-gray-500">{activeCategory.name}</span>
              <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {formatCurrency(activeCategory.amount)}
              </span>
              <span className="text-xs text-gray-500">{Math.round(activeCategory.pct * 100)}%</span>
            </>
          ) : (
            <>
              <span className="text-xs text-gray-500">Всего</span>
              <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {formatCurrency(total)}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Легенда — обязательна при ≥2 категорий (см. marks-and-anatomy.md):
          цвет никогда не единственный носитель идентичности, рядом всегда текст. */}
      {showLegend && (
      <ul className="flex w-full flex-col gap-2 text-sm">
        {segments.map((seg) => (
          <li
            key={seg.name}
            className={`flex items-center justify-between gap-3 rounded-md px-1.5 py-1 transition-colors ${
              hovered === seg.index ? 'bg-gray-100 dark:bg-gray-700' : ''
            }`}
            onMouseEnter={() => setHovered(seg.index)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="flex items-center gap-2 text-gray-700 dark:text-gray-200">
              <span
                className="h-2.5 w-2.5 flex-none rounded-full"
                style={{ backgroundColor: seg.color }}
                aria-hidden="true"
              />
              {seg.name}
            </span>
            <span className="flex-none font-medium tabular-nums text-gray-900 dark:text-gray-100">
              {formatCurrency(seg.amount)}
              <span className="ml-1.5 text-xs text-gray-500">{Math.round(seg.pct * 100)}%</span>
            </span>
          </li>
        ))}
      </ul>
      )}
    </div>
  )
}
