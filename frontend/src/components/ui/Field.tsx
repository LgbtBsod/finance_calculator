import type { ReactNode } from 'react'

interface FieldProps {
  label: string
  htmlFor?: string
  error?: string
  className?: string
  children: ReactNode
}

/** Обёртка label + control + сообщение об ошибке — аналог .form-group. */
export function Field({ label, htmlFor, error, className, children }: FieldProps) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-[13px] font-medium text-gray-500">
        {label}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  )
}

export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="mb-1 flex flex-wrap gap-4 [&>*]:min-w-[160px] [&>*]:flex-1">{children}</div>
}
