export function Spinner({ className = '' }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Загрузка"
      className={`h-4 w-4 animate-spin rounded-full border-2 border-gray-200 border-t-primary ${className}`}
    />
  )
}
