import { useEffect, type ReactNode } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

/**
 * Модалка для форм (создание/редактирование) — в отличие от ConfirmProvider
 * (промис-based, только да/нет), эта — обычный презентационный компонент:
 * состояние формы внутри неё живёт у вызывающей страницы, модалка просто
 * решает, показывать её или нет.
 *
 * Тот же aria-modal="true", что и у ConfirmProvider — глобальный "/"-шоткат
 * (см. ExpenseItemsPanel) уже умеет не перехватывать фокус, пока открыт
 * любой модальный диалог с этим атрибутом.
 */
export function Modal({ open, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (!open) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-2xl dark:bg-gray-800"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="focus-visible:ring-primary/40 flex-none rounded-full p-1.5 text-gray-400 transition-colors hover:bg-black/5 hover:text-gray-700 focus-visible:ring-3 focus-visible:outline-none dark:hover:text-gray-300"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
