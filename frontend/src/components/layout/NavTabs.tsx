import { NavLink } from 'react-router-dom'
import { cn } from '../../lib/cn'

// Баланс и ЗП живёт только в сайдбаре (см. Sidebar.tsx) — отдельной
// страницы/вкладки для него больше нет, поэтому здесь её нет в списке.
// Настройки открываются через отдельную шестерёнку в хедере (AppShell) —
// это редкое/служебное действие, а не один из основных разделов, вместе
// с которым не стоит толкаться среди часто используемых вкладок.
const LINKS = [
  { to: '/', label: '📈 Аналитика' },
  { to: '/expenses', label: '💸 Расходы' },
  { to: '/vacations', label: '🏖️ Отпускные' },
  { to: '/birthdays', label: '🎂 Дни рождения' },
  { to: '/debts', label: '💳 Долги' },
] as const

/**
 * Реальная навигация (React Router), а не переключение .active на панелях
 * одной страницы — поэтому здесь обычная семантика <nav>/ссылки, а не
 * самодельный ARIA tabs-паттерн: скринридеры и так умеют работать со
 * списком ссылок, изобретать роль tab/tabpanel не нужно (не переусложняем).
 */
export function NavTabs() {
  return (
    <nav
      aria-label="Разделы приложения"
      className="mb-6 flex flex-wrap gap-1 rounded-full bg-gray-100 p-1 dark:bg-gray-800"
    >
      {LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          end={link.to === '/'}
          className={({ isActive }) =>
            cn(
              'flex-1 rounded-full px-4 py-2.5 text-center text-[15px] font-medium whitespace-nowrap transition-colors',
              isActive
                ? 'bg-white text-primary shadow-card dark:bg-gray-900'
                : 'text-gray-500 hover:bg-black/5 hover:text-gray-900 dark:hover:text-gray-100',
            )
          }
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  )
}
