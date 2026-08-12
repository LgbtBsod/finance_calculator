import { useCallback, useEffect, useRef, useState } from 'react'
import { useToast } from '../components/ui/ToastProvider'

// Должно совпадать с ACTION_DISPLAY_MS в ToastProvider — тост с "Отменить"
// обязан жить не меньше самого окна отмены.
const UNDO_WINDOW_MS = 5000

interface PendingDelete {
  timeoutId: ReturnType<typeof setTimeout>
  performDelete: () => void
}

/**
 * Мягкое удаление: сразу прячет элемент из списка (см. isPending), но
 * реальный DELETE-запрос откладывается на UNDO_WINDOW_MS — окно, за которое
 * пользователь может нажать "Отменить" в тосте и вернуть элемент как ни в
 * чём не бывало. Confirm-диалог ("Удалить «X»?") остаётся ДО вызова
 * scheduleDelete — это не замена подтверждению, а вторая, более мягкая
 * страховка на случай "подтвердил не то" или "передумал".
 */
export function useUndoableDelete<TId extends string | number>() {
  const [pendingIds, setPendingIds] = useState<Set<TId>>(new Set())
  const pending = useRef<Map<TId, PendingDelete>>(new Map())
  const { showActionToast } = useToast()

  // Если компонент размонтируется раньше, чем истечёт окно (переход на
  // другую страницу) — выполняем отложенные удаления немедленно, а не
  // тихо отменяем их: пользователь уже подтвердил удаление и не успел
  // нажать "Отменить", так что запись не должна остаться в БД молча.
  useEffect(() => {
    const stillPending = pending.current
    return () => {
      stillPending.forEach(({ timeoutId, performDelete }) => {
        clearTimeout(timeoutId)
        performDelete()
      })
    }
  }, [])

  const scheduleDelete = useCallback(
    (id: TId, message: string, performDelete: () => void) => {
      setPendingIds((prev) => new Set(prev).add(id))

      const timeoutId = setTimeout(() => {
        pending.current.delete(id)
        setPendingIds((prev) => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
        performDelete()
      }, UNDO_WINDOW_MS)
      pending.current.set(id, { timeoutId, performDelete })

      showActionToast(message, 'Отменить', () => {
        const entry = pending.current.get(id)
        if (entry) {
          clearTimeout(entry.timeoutId)
          pending.current.delete(id)
        }
        setPendingIds((prev) => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
      })
    },
    [showActionToast],
  )

  const isPending = useCallback((id: TId) => pendingIds.has(id), [pendingIds])

  return { isPending, scheduleDelete }
}
