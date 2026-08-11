import { describe, expect, it } from 'vitest'
import { formatCurrency, formatDateLongRu, formatDateRu, pluralizeRu } from './format'

describe('formatCurrency', () => {
  it('formats whole rubles without decimals', () => {
    expect(formatCurrency(87000)).toContain('87')
    expect(formatCurrency(87000)).toContain('000')
  })

  it('defaults to 0 for null/undefined', () => {
    expect(formatCurrency(null)).toBe(formatCurrency(0))
    expect(formatCurrency(undefined)).toBe(formatCurrency(0))
  })
})

describe('formatDateRu', () => {
  it('converts ISO date to DD.MM.YYYY', () => {
    expect(formatDateRu('2025-07-04')).toBe('04.07.2025')
  })

  it('handles datetime strings by taking only the date part', () => {
    expect(formatDateRu('2025-07-04T12:30:00')).toBe('04.07.2025')
  })

  it('returns empty string for falsy input', () => {
    expect(formatDateRu(null)).toBe('')
    expect(formatDateRu('')).toBe('')
  })
})

describe('formatDateLongRu', () => {
  it('formats with genitive month name', () => {
    expect(formatDateLongRu('2026-08-10')).toBe('10 августа 2026')
    expect(formatDateLongRu('2025-12-30')).toBe('30 декабря 2025')
    expect(formatDateLongRu('2026-01-23')).toBe('23 января 2026')
  })

  it('returns empty string for falsy input', () => {
    expect(formatDateLongRu(null)).toBe('')
    expect(formatDateLongRu('')).toBe('')
  })
})

describe('pluralizeRu', () => {
  const forms = (n: number) => pluralizeRu(n, 'расход', 'расхода', 'расходов')

  it('uses "one" form for numbers ending in 1 (except 11)', () => {
    expect(forms(1)).toBe('расход')
    expect(forms(21)).toBe('расход')
    expect(forms(101)).toBe('расход')
  })

  it('uses "few" form for 2-4 (except 12-14)', () => {
    expect(forms(2)).toBe('расхода')
    expect(forms(3)).toBe('расхода')
    expect(forms(4)).toBe('расхода')
    expect(forms(22)).toBe('расхода')
  })

  it('uses "many" form for 0, 5-20, and 11-14 specifically', () => {
    expect(forms(0)).toBe('расходов')
    expect(forms(5)).toBe('расходов')
    expect(forms(11)).toBe('расходов')
    expect(forms(12)).toBe('расходов')
    expect(forms(13)).toBe('расходов')
    expect(forms(14)).toBe('расходов')
    expect(forms(20)).toBe('расходов')
  })

  it('handles the "1 запись" edge case from the old analytics bug', () => {
    expect(pluralizeRu(1, 'запись', 'записи', 'записей')).toBe('запись')
  })
})
