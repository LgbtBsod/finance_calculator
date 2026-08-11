import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export type CardVariant = 'default' | 'success' | 'warning' | 'accent'

const VARIANT_CLASSES: Record<CardVariant, string> = {
  default: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-inherit',
  success: 'bg-gradient-to-br from-success to-[#30b850] text-white border-none',
  warning: 'bg-gradient-to-br from-warning to-[#ff7a00] text-white border-none',
  accent: 'bg-gradient-to-br from-primary to-[#5856d6] text-white border-none',
}

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant
}

/** Базовая карточка приложения — соответствует .card/.card.green/.card.orange из старого styles.css. */
export function Card({ variant = 'default', className, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-lg p-5 shadow-card transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-card-hover',
        VARIANT_CLASSES[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardTitle({ className, children, ...rest }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn('mb-2 text-sm font-semibold opacity-90', className)} {...rest}>
      {children}
    </h3>
  )
}

export function CardAmount({ className, children, ...rest }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('text-2xl font-bold tracking-tight tabular-nums', className)} {...rest}>
      {children}
    </p>
  )
}

export function CardGrid({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3', className)}
      {...rest}
    >
      {children}
    </div>
  )
}
