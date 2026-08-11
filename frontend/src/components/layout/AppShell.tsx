import { Outlet } from 'react-router-dom'
import { NavTabs } from './NavTabs'
import { Sidebar } from './Sidebar'

export function AppShell() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-5 pb-16 sm:px-5">
      <header className="mb-6">
        <h1 className="mb-1.5 bg-gradient-to-br from-primary to-[#5856d6] bg-clip-text text-3xl font-bold tracking-tight text-transparent">
          💰 Личный финансовый калькулятор
        </h1>
      </header>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <aside className="w-full flex-none overflow-y-auto lg:sticky lg:top-5 lg:max-h-[calc(100vh-2.5rem)] lg:w-80">
          <Sidebar />
        </aside>

        <div className="min-w-0 flex-1">
          <NavTabs />
          <main>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
