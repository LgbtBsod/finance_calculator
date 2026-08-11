import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface StickyFormColumnProps {
  /** Управляющий блок колонки (форма создания/редактирования, фильтры,
   * кнопки массовых действий) — всегда виден целиком, не скроллится. */
  form: ReactNode
  /** Список объектов колонки — скроллится в своей области, не затрагивая форму. */
  children: ReactNode
  className?: string
}

/**
 * Layout-примитив для колонок "управление + список": форма — обычный,
 * никогда не скроллящийся блок сверху; список ниже занимает остаток
 * высоты колонки и скроллится сам в себе (`overflow-y-auto`), когда не
 * помещается. Высота берётся из родителя обычным flexbox-наследованием
 * (`h-full` до самого AppShell, см. его комментарий) — никаких
 * `position: sticky` и посчитанных на глаз `calc(100vh-...)`: sticky-блок
 * красится НАД обычным потоком независимо от DOM-порядка, из-за чего
 * доскроленный список залезал под форму. Контейнерная модель с реальной
 * высотой этой проблемы не имеет.
 *
 * Используется в ExpensesPage (расходы / группы) и BirthdaysPage (дни
 * рождения / напоминания) — единая реализация вместо двух похожих
 * раскладок (DRY).
 */
export function StickyFormColumn({ form, children, className }: StickyFormColumnProps) {
  return (
    <div className={cn('flex flex-col gap-4 xl:h-full xl:min-h-0', className)}>
      <div className="flex-none">{form}</div>
      <div className="min-h-0 xl:flex-1 xl:overflow-y-auto xl:pr-1">{children}</div>
    </div>
  )
}
