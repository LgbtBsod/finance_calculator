/** Прогноз погашения долга — чистые функции, без сети/React, легко тестируются. */

export interface RepaymentLike {
  amount: number
  date: string // 'YYYY-MM-DD'
}

export interface DebtProjection {
  /** Средний темп погашения, ₽/мес, по фактической истории платежей. */
  avgMonthlyRate: number
  /** null — если темп неизвестен (нет платежей) или неположителен. */
  monthsToPayoff: number | null
  projectedDate: Date | null
}

function monthsBetween(from: Date, to: Date): number {
  return (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth())
}

export function addMonths(date: Date, months: number): Date {
  const d = new Date(date)
  d.setMonth(d.getMonth() + months)
  return d
}

/**
 * Прогноз "при текущем темпе" — темп считается как весь погашенный остаток
 * делённый на число месяцев с ПЕРВОГО платежа (включительно), а не только
 * по месяцам, где были платежи: нерегулярные платежи (раз в квартал и т.п.)
 * должны честно давать более медленный, а не завышенный темп.
 */
export function projectDebtPayoff(
  remainingAmount: number,
  repayments: RepaymentLike[],
  today: Date = new Date(),
): DebtProjection {
  if (remainingAmount <= 0 || repayments.length === 0) {
    return { avgMonthlyRate: 0, monthsToPayoff: null, projectedDate: null }
  }

  const earliest = repayments.reduce(
    (min, r) => (new Date(r.date) < min ? new Date(r.date) : min),
    new Date(repayments[0].date),
  )
  const monthsElapsed = Math.max(1, monthsBetween(earliest, today) + 1)
  const totalRepaid = repayments.reduce((sum, r) => sum + r.amount, 0)
  const avgMonthlyRate = totalRepaid / monthsElapsed

  if (avgMonthlyRate <= 0) {
    return { avgMonthlyRate, monthsToPayoff: null, projectedDate: null }
  }

  const monthsToPayoff = Math.ceil(remainingAmount / avgMonthlyRate)
  return { avgMonthlyRate, monthsToPayoff, projectedDate: addMonths(today, monthsToPayoff) }
}

/** Прогноз "что если платить X ₽/мес" — для гипотетической суммы из инпута. */
export function projectPayoffAtRate(
  remainingAmount: number,
  monthlyRate: number,
  today: Date = new Date(),
): Date | null {
  if (remainingAmount <= 0) return null
  if (!(monthlyRate > 0)) return null
  const months = Math.ceil(remainingAmount / monthlyRate)
  return addMonths(today, months)
}
