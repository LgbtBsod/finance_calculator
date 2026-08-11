import { describe, expect, it } from 'vitest'
import {
  buildBirthDateForApi,
  formatBirthDateRu,
  formatCurrency,
  formatDateLongRu,
  formatDateRu,
  parseBirthDate,
  pluralizeRu,
} from './format'

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

describe('buildBirthDateForApi', () => {
  it('pads day/month and appends the fixed leap-year placeholder', () => {
    expect(buildBirthDateForApi(5, 3)).toBe('05.03.2000')
    expect(buildBirthDateForApi(29, 2)).toBe('29.02.2000') // 2000 — високосный, 29 февраля валидно
    expect(buildBirthDateForApi(20, 12)).toBe('20.12.2000')
  })
})

describe('parseBirthDate', () => {
  it('extracts day and month, ignoring the year', () => {
    expect(parseBirthDate('15.03.1990')).toEqual({ day: 15, month: 3 })
    expect(parseBirthDate('01.01.2000')).toEqual({ day: 1, month: 1 })
  })

  it('returns null for malformed input', () => {
    expect(parseBirthDate('not-a-date')).toBeNull()
    expect(parseBirthDate('')).toBeNull()
  })
})

describe('formatBirthDateRu', () => {
  it('formats as "день месяц" without the year', () => {
    expect(formatBirthDateRu('15.03.1990')).toBe('15 марта')
    expect(formatBirthDateRu('01.01.2000')).toBe('1 января')
  })

  it('falls back to the raw string for malformed input', () => {
    expect(formatBirthDateRu('garbage')).toBe('garbage')
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
