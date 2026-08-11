import { forwardRef, type SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          'w-full rounded-md border border-gray-300 bg-white px-4 py-3 text-[15px] text-gray-900 outline-none transition-[border-color,box-shadow] focus:border-primary focus:ring-3 focus:ring-primary/15 dark:bg-gray-800 dark:text-gray-100',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    )
  },
)
