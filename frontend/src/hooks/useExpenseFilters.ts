import { useMemo, useState } from 'react'
import type { ExpenseItem } from './useExpenses'

export type ExpenseSortOption = 'date-desc' | 'date-asc' | 'amount-desc' | 'amount-asc'

export const EXPENSE_PAGE_SIZE = 20

// Сортировочный ключ без разбора реальных календарных дат — half здесь
// заменяет "день": в рамках месяца 1-я половина всегда раньше 2-й.
function sortKey(item: ExpenseItem): number {
  return item.year * 10000 + item.month * 10 + item.half
}

/**
 * Уточняющие клиентские фильтры + сортировка + пагинация над уже
 * загруженным (по месяцу/году или "за все периоды") списком расходов.
 * Выделено из ExpensesPage — раньше все 4 фильтра, сортировка и
 * производные списки жили в одном god-компоненте вперемешку с формами.
 */
export function useExpenseFilters(items: ExpenseItem[]) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterGroupId, setFilterGroupId] = useState('')
  const [filterHalf, setFilterHalf] = useState<'' | '1' | '2'>('')
  const [recurringOnly, setRecurringOnly] = useState(false)
  const [sortBy, setSortBy] = useState<ExpenseSortOption>('date-desc')
  const [page, setPage] = useState(1)

  const hasActiveFilters =
    searchQuery.trim() !== '' || filterGroupId !== '' || filterHalf !== '' || recurringOnly

  const visibleItems = useMemo(() => {
    let result = items
    if (hasActiveFilters) {
      const query = searchQuery.trim().toLowerCase()
      result = result.filter((item) => {
        if (query && !item.name.toLowerCase().includes(query)) return false
        if (filterGroupId === '__none__' && item.groupId) return false
        if (filterGroupId && filterGroupId !== '__none__' && item.groupId !== filterGroupId) return false
        if (filterHalf && String(item.half) !== filterHalf) return false
        if (recurringOnly && !item.isRecurring) return false
        return true
      })
    }
    return [...result].sort((a, b) => {
      switch (sortBy) {
        case 'date-asc':
          return sortKey(a) - sortKey(b)
        case 'amount-desc':
          return b.amount - a.amount
        case 'amount-asc':
          return a.amount - b.amount
        case 'date-desc':
        default:
          return sortKey(b) - sortKey(a)
      }
    })
  }, [items, hasActiveFilters, searchQuery, filterGroupId, filterHalf, recurringOnly, sortBy])

  const totalPages = Math.max(1, Math.ceil(visibleItems.length / EXPENSE_PAGE_SIZE))

  // Сброс на 1-ю страницу при любом изменении видимого набора — иначе
  // легко "залипнуть" на странице, которой больше не существует (пустой
  // экран без объяснения) после смены фильтра/сортировки/периода. Делаем
  // это прямо в теле рендера ("adjusting state when a prop changes" —
  // react.dev/learn/you-might-not-need-an-effect), а не в useEffect: иначе
  // это лишний лишний повторный рендер после коммита ради того же результата.
  // Сигнатура — набор id, а не сама ссылка на items: фоновый рефетч с тем
  // же содержимым не должен сбрасывать страницу пользователю под ногами.
  const resetSignature = `${items.map((i) => i.id).join(',')}|${searchQuery}|${filterGroupId}|${filterHalf}|${recurringOnly}|${sortBy}`
  const [prevResetSignature, setPrevResetSignature] = useState(resetSignature)
  if (resetSignature !== prevResetSignature) {
    setPrevResetSignature(resetSignature)
    setPage(1)
  }

  const pagedItems = useMemo(
    () => visibleItems.slice((page - 1) * EXPENSE_PAGE_SIZE, page * EXPENSE_PAGE_SIZE),
    [visibleItems, page],
  )

  function resetFilters() {
    setSearchQuery('')
    setFilterGroupId('')
    setFilterHalf('')
    setRecurringOnly(false)
  }

  return {
    searchQuery,
    setSearchQuery,
    filterGroupId,
    setFilterGroupId,
    filterHalf,
    setFilterHalf,
    recurringOnly,
    setRecurringOnly,
    sortBy,
    setSortBy,
    hasActiveFilters,
    resetFilters,
    visibleItems,
    pagedItems,
    page,
    setPage,
    totalPages,
  }
}
