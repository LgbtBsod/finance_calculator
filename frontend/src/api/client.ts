/**
 * Типизированный API-клиент поверх сгенерированной OpenAPI-схемы.
 *
 * Схема (schema.d.ts) генерируется командой `npm run gen:api` из живой
 * FastAPI-схемы (/openapi.json) — вручную дублировать типы не нужно (DRY,
 * SSOT: контракт живёт в одном месте, в api.py).
 */
import createClient from 'openapi-fetch'
import type { paths } from './schema'

export const apiClient = createClient<paths>({ baseUrl: '/' })

export type { components } from './schema'
