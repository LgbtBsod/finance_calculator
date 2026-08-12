import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'success' | 'danger' | 'ghost'

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover',
  success: 'bg-success text-white hover:bg-[#2aab4b]',
  danger: 'bg-danger text-white hover:bg-[#e0342a]',
  ghost: 'bg-transparent text-gray-500 hover:opacity-100 opacity-60',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: 'sm' | 'md'
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-transform active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50',
        // Input/Select/Switch уже имели брендированное focus-ring — кнопки и
        // навигация обходились нативным outline браузера. Один и тот же
        // стиль фокуса на всём интерактиве приложения.
        'focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/40',
        size === 'md' ? 'px-5 py-3 text-[15px]' : 'px-3.5 py-2 text-[13px]',
        VARIANT_CLASSES[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
