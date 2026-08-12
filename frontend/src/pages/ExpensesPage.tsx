import { useState } from 'react'
import { ExpenseItemsPanel } from './expenses/ExpenseItemsPanel'
import { ExpenseGroupsPanel } from './expenses/ExpenseGroupsPanel'

/**
 * Тонкая композиция двух панелей — сама страница больше не хранит
 * состояние форм/фильтров расходов и групп (см. ExpenseItemsPanel,
 * ExpenseGroupsPanel, useExpenseFilters). Из общего состояния здесь
 * остался только выбор периода (месяц/год/"все периоды") — он нужен
 * обеим панелям одновременно: ExpenseItemsPanel фильтрует по нему сам
 * список расходов, а ExpenseGroupsPanel считает счётчик "N расходов"
 * у каждой группы за тот же период.
 */
export function ExpensesPage() {
  const now = new Date()
  const [filterMonth, setFilterMonth] = useState(now.getMonth() + 1)
  const [filterYear, setFilterYear] = useState(now.getFullYear())
  const [showAllPeriods, setShowAllPeriods] = useState(false)

  return (
    <div className="grid grid-cols-1 gap-8 xl:h-full xl:grid-cols-[1fr_22rem]">
      {/* ЦЕНТР: расходы — основной объект этой страницы */}
      <ExpenseItemsPanel
        filterMonth={filterMonth}
        filterYear={filterYear}
        showAllPeriods={showAllPeriods}
        onFilterMonthChange={setFilterMonth}
        onFilterYearChange={setFilterYear}
        onShowAllPeriodsChange={setShowAllPeriods}
      />

      {/* СПРАВА: группы расходов — вторичное управление */}
      <ExpenseGroupsPanel filterMonth={filterMonth} filterYear={filterYear} showAllPeriods={showAllPeriods} />
    </div>
  )
}
