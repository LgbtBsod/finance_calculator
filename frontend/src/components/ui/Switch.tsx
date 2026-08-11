import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

type SwitchProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

/**
 * Переключатель на основе настоящего <input type="checkbox"> — сохраняет
 * нативную клавиатурную/скринридер-доступность и совместимость с
 * react-hook-form's register() (которому нужен реальный checkbox-инпут),
 * но визуально выглядит как iOS-style свитч через peer-варианты Tailwind.
 */
export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { className, ...rest },
  ref,
) {
  return (
    <span className="relative inline-flex h-6 w-11 flex-none items-center">
      <input
        ref={ref}
        type="checkbox"
        className={cn('peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0', className)}
        {...rest}
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-full bg-gray-300 transition-colors peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-primary/40 dark:bg-gray-600"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5"
      />
    </span>
  )
})
