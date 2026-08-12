import { lazy } from 'react'

// Ленивые (route-level) обёртки над страницами: каждая страница экспортируется
// именованно (не default), поэтому React.lazy() оборачивается в .then(), чтобы
// подсунуть ему требуемый default-экспорт. Вынесено в отдельный файл, чтобы
// react-refresh/only-export-components не жаловался на router.tsx, где рядом
// есть неигровой (не-компонентный) экспорт `router`.
export const AnalyticsPage = lazy(() =>
  import('./AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })),
)
export const ExpensesPage = lazy(() =>
  import('./ExpensesPage').then((m) => ({ default: m.ExpensesPage })),
)
export const VacationsPage = lazy(() =>
  import('./VacationsPage').then((m) => ({ default: m.VacationsPage })),
)
export const BirthdaysPage = lazy(() =>
  import('./BirthdaysPage').then((m) => ({ default: m.BirthdaysPage })),
)
export const DebtsPage = lazy(() =>
  import('./DebtsPage').then((m) => ({ default: m.DebtsPage })),
)
export const SettingsPage = lazy(() =>
  import('./SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
