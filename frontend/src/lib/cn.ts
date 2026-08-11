/** Малый помощник для условных className-строк — не тащим classnames/clsx под одну функцию. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
