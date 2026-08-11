/** Форматирование сумм, дат и русских числительных — общие для всех страниц. */

export function formatCurrency(amount: number | null | undefined): string {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
  }).format(amount ?? 0)
}

/** 'YYYY-MM-DD' -> 'DD.MM.YYYY' */
export function formatDateRu(isoDate: string | null | undefined): string {
  if (!isoDate) return ''
  const [y, m, d] = isoDate.slice(0, 10).split('-')
  return `${d}.${m}.${y}`
}

const MONTH_NAMES_GENITIVE_RU = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
] as const

/** 'YYYY-MM-DD' -> '10 августа 2026' */
export function formatDateLongRu(isoDate: string | null | undefined): string {
  if (!isoDate) return ''
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  return `${d} ${MONTH_NAMES_GENITIVE_RU[m - 1]} ${y}`
}

/**
 * Год в датах дней рождения функционально не используется (BirthdayService
 * учитывает только день+месяц), поэтому в UI мы его не спрашиваем — при
 * отправке на сервер (который требует полную дату DD.MM.YYYY) подставляем
 * этот фиксированный високосный год, чтобы 29 февраля тоже проходило
 * валидацию.
 */
export const BIRTHDAY_PLACEHOLDER_YEAR = 2000

/** (15, 3) -> '15.03.2000' — для отправки на backend. */
export function buildBirthDateForApi(day: number, month: number): string {
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${BIRTHDAY_PLACEHOLDER_YEAR}`
}

/** 'DD.MM.YYYY' -> {day, month}; год отбрасывается — он не имеет значения. */
export function parseBirthDate(birthDate: string): { day: number; month: number } | null {
  const [d, m] = birthDate.split('.').map(Number)
  if (!d || !m) return null
  return { day: d, month: m }
}

/** 'DD.MM.YYYY' -> '15 марта' — без года, который для ДР не важен. */
export function formatBirthDateRu(birthDate: string): string {
  const parsed = parseBirthDate(birthDate)
  if (!parsed) return birthDate
  return `${parsed.day} ${MONTH_NAMES_GENITIVE_RU[parsed.month - 1]}`
}

/**
 * Русские окончания по числительным: 1 расход / 2 расхода / 5 расходов.
 * Правило: 11-14 всегда "many"; иначе по последней цифре.
 */
export function pluralizeRu(n: number, one: string, few: string, many: string): string {
  const mod10 = Math.abs(n) % 10
  const mod100 = Math.abs(n) % 100
  if (mod100 >= 11 && mod100 <= 14) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

export const MONTH_NAMES_RU = [
  '',
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
] as const
