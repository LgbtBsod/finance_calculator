import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Button } from './Button'

interface ConfirmOptions {
  title: string
  danger?: boolean
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFn | null>(null)

interface PendingConfirm extends ConfirmOptions {
  resolve: (value: boolean) => void
}

/** Промис-based модалка подтверждения — замена window.confirm() в стиле приложения. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null)

  const confirm = useCallback<ConfirmFn>((options) => {
    return new Promise<boolean>((resolve) => {
      setPending({ ...options, resolve })
    })
  }, [])

  const close = (result: boolean) => {
    pending?.resolve(result)
    setPending(null)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {pending && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="alertdialog"
          aria-modal="true"
          aria-label={pending.title}
          onClick={() => close(false)}
        >
          <div
            className="w-full max-w-sm rounded-lg bg-white p-6 shadow-2xl dark:bg-gray-800"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="mb-5 text-[15px] font-medium text-gray-900 dark:text-gray-100">
              {pending.title}
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => close(false)}>
                Отмена
              </Button>
              <Button variant={pending.danger ? 'danger' : 'primary'} onClick={() => close(true)}>
                Подтвердить
              </Button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm() must be used within <ConfirmProvider>')
  return ctx
}
