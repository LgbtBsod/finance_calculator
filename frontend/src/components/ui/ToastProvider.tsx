import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: number
  message: string
  type: ToastType
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS: Record<ToastType, string> = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
}

const BORDER_CLASSES: Record<ToastType, string> = {
  success: 'border-l-success',
  error: 'border-l-danger',
  warning: 'border-l-warning',
  info: 'border-l-primary',
}

const DISPLAY_MS = 3000
const EXIT_ANIMATION_MS = 250

/** Провайдер тостов — функциональный аналог showToast() из старого app.js. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [exiting, setExiting] = useState<Set<number>>(new Set())
  const nextId = useRef(0)

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = nextId.current++
    setToasts((prev) => [...prev, { id, message, type }])

    setTimeout(() => {
      setExiting((prev) => new Set(prev).add(id))
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
        setExiting((prev) => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
      }, EXIT_ANIMATION_MS)
    }, DISPLAY_MS)
  }, [])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed top-5 right-5 z-50 flex flex-col gap-3"
        style={{ top: 'calc(20px + env(safe-area-inset-top, 0px))' }}
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex max-w-[350px] items-center gap-3 rounded-xl border-l-4 bg-white p-4 shadow-2xl ${BORDER_CLASSES[toast.type]} ${exiting.has(toast.id) ? 'animate-toast-out' : 'animate-toast-in'}`}
          >
            <span className="text-lg">{ICONS[toast.type]}</span>
            <span className="text-sm font-medium text-gray-800">{toast.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast() must be used within <ToastProvider>')
  return ctx
}
