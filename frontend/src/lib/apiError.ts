/** Достаёт человекочитаемое сообщение из ошибки FastAPI ({ detail: string | ValidationError[] }).
 *
 * Раньше жила только в useVacations.ts — остальные mutation-хуки (useExpenses,
 * useBirthdays, useDebts, useSettings) при ошибке бросали один и тот же
 * хардкод-текст, полностью отбрасывая detail от backend (например, конкретную
 * причину 400 "Неверный формат даты..." пользователь никогда не видел).
 * Общая версия здесь — используется одинаково во всех mutation-хуках.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.length > 0) return detail
  }
  return fallback
}

/** Ошибка API с HTTP-статусом — например, чтобы отличить "запись удалили в
 * другой вкладке" (404) от прочих ошибок сохранения и явно закрыть форму
 * редактирования вместо бесконечного повторения того же неинформативного
 * тоста при повторном нажатии "Сохранить". */
export class ApiError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function toApiError(error: unknown, fallback: string, status?: number): ApiError {
  return new ApiError(extractErrorMessage(error, fallback), status)
}
