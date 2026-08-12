import { describe, expect, it } from 'vitest'
import { addMonths, projectDebtPayoff, projectPayoffAtRate } from './debtProjection'

describe('projectDebtPayoff', () => {
  it('returns no projection when there are no repayments yet', () => {
    const result = projectDebtPayoff(10000, [])
    expect(result.monthsToPayoff).toBeNull()
    expect(result.projectedDate).toBeNull()
  })

  it('returns no projection when the debt is already paid off', () => {
    const result = projectDebtPayoff(0, [{ amount: 1000, date: '2026-01-01' }])
    expect(result.monthsToPayoff).toBeNull()
  })

  it('computes average monthly rate over months elapsed since the first repayment, not just active months', () => {
    const today = new Date('2026-04-15')
    // Один платёж 3000 в январе -> 4 месяца (янв-апр включительно) -> 750/мес,
    // а не 3000/мес (что было бы, если бы считали только "активные" месяцы).
    const result = projectDebtPayoff(10000, [{ amount: 3000, date: '2026-01-10' }], today)
    expect(result.avgMonthlyRate).toBeCloseTo(750, 0)
  })

  it('projects a payoff date consistent with the computed rate', () => {
    const today = new Date('2026-01-15')
    // 1 платёж 1000 в этом же месяце -> темп 1000/мес, остаток 5000 -> 5 месяцев.
    const result = projectDebtPayoff(5000, [{ amount: 1000, date: '2026-01-05' }], today)
    expect(result.monthsToPayoff).toBe(5)
    expect(result.projectedDate).toEqual(addMonths(today, 5))
  })

  it('uses the earliest repayment date even if repayments are out of order', () => {
    const today = new Date('2026-06-15')
    const result = projectDebtPayoff(
      10000,
      [
        { amount: 1000, date: '2026-05-01' },
        { amount: 1000, date: '2026-01-01' }, // самый ранний, хотя не первый в массиве
      ],
      today,
    )
    // янв-июн включительно = 6 месяцев, всего погашено 2000 -> ~333.33/мес
    expect(result.avgMonthlyRate).toBeCloseTo(2000 / 6, 1)
  })
})

describe('projectPayoffAtRate', () => {
  it('returns null for a zero or negative rate', () => {
    expect(projectPayoffAtRate(5000, 0)).toBeNull()
    expect(projectPayoffAtRate(5000, -100)).toBeNull()
  })

  it('returns null when the debt is already paid off', () => {
    expect(projectPayoffAtRate(0, 1000)).toBeNull()
  })

  it('rounds up to the next whole month', () => {
    const today = new Date('2026-01-01')
    // 5000 / 2000 = 2.5 -> округляем вверх до 3 месяцев.
    const result = projectPayoffAtRate(5000, 2000, today)
    expect(result).toEqual(addMonths(today, 3))
  })
})

describe('addMonths', () => {
  it('rolls over into the next year', () => {
    const result = addMonths(new Date('2026-11-15'), 3)
    expect(result.getFullYear()).toBe(2027)
    expect(result.getMonth()).toBe(1) // февраль (0-indexed)
  })
})
