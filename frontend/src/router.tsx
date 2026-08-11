import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { ExpensesPage } from './pages/ExpensesPage'
import { VacationsPage } from './pages/VacationsPage'
import { BirthdaysPage } from './pages/BirthdaysPage'
import { DebtsPage } from './pages/DebtsPage'
import { SettingsPage } from './pages/SettingsPage'

// Баланс и ЗП больше не отдельная страница — он всегда виден в сайдбаре
// (см. components/layout/Sidebar.tsx), поэтому индексный маршрут теперь
// ведёт на Аналитику, а не на бывшую BalancePage.
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <AnalyticsPage /> },
      { path: 'expenses', element: <ExpensesPage /> },
      { path: 'vacations', element: <VacationsPage /> },
      { path: 'birthdays', element: <BirthdaysPage /> },
      { path: 'debts', element: <DebtsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
])
