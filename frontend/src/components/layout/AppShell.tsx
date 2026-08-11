import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { NavTabs } from './NavTabs'
import { Sidebar } from './Sidebar'

/**
 * На lg+ вся оболочка занимает ровно высоту вьюпорта (`h-dvh`) и сама
 * никогда не скроллится — скроллятся только сайдбар и `<main>`
 * независимо друг от друга. Раньше сайдбар был `sticky` внутри
 * скроллящейся страницы: работало, но при большом списке в контентной
 * области получалось до трёх независимых скроллов одновременно (страница
 * + список расходов + список групп) — сбивало с толку. Один явный скролл
 * на каждую область — предсказуемее. На мобильных (< lg) всё остаётся
 * простым вертикальным потоком, как раньше — там нет места для колонок,
 * и обычный скролл страницы ощущается естественно.
 */
export function AppShell() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col px-4 pt-5 pb-16 sm:px-5 lg:h-dvh lg:pb-5">
      <header className="mb-6 flex flex-none items-start justify-between gap-4">
        <h1 className="mb-1.5 bg-gradient-to-br from-primary to-[#5856d6] bg-clip-text text-3xl font-bold tracking-tight text-transparent">
          💰 Личный финансовый калькулятор
        </h1>
        <NavLink
          to="/settings"
          aria-label="Настройки"
          className={({ isActive }) =>
            cn(
              'flex-none rounded-full p-2.5 text-xl transition-colors',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-gray-400 hover:bg-black/5 hover:text-gray-700 dark:hover:text-gray-300',
            )
          }
        >
          ⚙️
        </NavLink>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
        <aside className="w-full flex-none lg:h-full lg:w-80 lg:overflow-y-auto">
          <Sidebar />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col lg:min-h-0">
          <NavTabs />
          <main className="flex-1 lg:min-h-0 lg:overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
