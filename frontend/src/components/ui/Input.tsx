import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, type = 'text', ...rest }, ref) {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          'w-full rounded-md border border-gray-300 bg-white px-4 py-3 text-[15px] text-gray-900 outline-none transition-[border-color,box-shadow] focus:border-primary focus:ring-3 focus:ring-primary/15 dark:bg-gray-800 dark:text-gray-100',
          type === 'color' && 'h-12 w-16 cursor-pointer p-1',
          type === 'checkbox' && 'h-[18px] w-[18px] accent-primary',
          className,
        )}
        {...rest}
      />
    )
  },
)
