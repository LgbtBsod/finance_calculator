import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUndoableDelete } from './useUndoableDelete'

const showActionToast = vi.fn()

vi.mock('../components/ui/ToastProvider', () => ({
  useToast: () => ({ showActionToast, showToast: vi.fn() }),
}))

describe('useUndoableDelete', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    showActionToast.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('marks the id as pending immediately and calls performDelete only after the undo window elapses', () => {
    const performDelete = vi.fn()
    const { result } = renderHook(() => useUndoableDelete<string>())

    act(() => {
      result.current.scheduleDelete('1', 'Долг удалён', performDelete)
    })

    expect(result.current.isPending('1')).toBe(true)
    expect(performDelete).not.toHaveBeenCalled()
    expect(showActionToast).toHaveBeenCalledWith('Долг удалён', 'Отменить', expect.any(Function))

    act(() => {
      vi.advanceTimersByTime(4999)
    })
    expect(performDelete).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(performDelete).toHaveBeenCalledTimes(1)
    expect(result.current.isPending('1')).toBe(false)
  })

  it('cancels the pending deletion and clears isPending when the toast action fires before the window elapses', () => {
    const performDelete = vi.fn()
    const { result } = renderHook(() => useUndoableDelete<string>())

    act(() => {
      result.current.scheduleDelete('1', 'Долг удалён', performDelete)
    })
    expect(result.current.isPending('1')).toBe(true)

    // showActionToast(message, label, onAction) — onAction — это ровно тот
    // колбэк, который вызовется по клику "Отменить" в реальном тосте.
    const onAction = showActionToast.mock.calls[0][2] as () => void

    act(() => {
      vi.advanceTimersByTime(2000)
      onAction()
    })
    expect(result.current.isPending('1')).toBe(false)

    act(() => {
      vi.advanceTimersByTime(10000)
    })
    expect(performDelete).not.toHaveBeenCalled()
  })

  it('tracks multiple pending ids independently', () => {
    const performDeleteA = vi.fn()
    const performDeleteB = vi.fn()
    const { result } = renderHook(() => useUndoableDelete<string>())

    act(() => {
      result.current.scheduleDelete('a', 'A удалён', performDeleteA)
    })
    act(() => {
      vi.advanceTimersByTime(2000)
      result.current.scheduleDelete('b', 'B удалён', performDeleteB)
    })

    expect(result.current.isPending('a')).toBe(true)
    expect(result.current.isPending('b')).toBe(true)

    // A был запланирован на 2с раньше -> срабатывает первым.
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(performDeleteA).toHaveBeenCalledTimes(1)
    expect(performDeleteB).not.toHaveBeenCalled()
    expect(result.current.isPending('a')).toBe(false)
    expect(result.current.isPending('b')).toBe(true)

    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(performDeleteB).toHaveBeenCalledTimes(1)
  })

  it('performs any still-pending deletions immediately on unmount instead of silently dropping them', () => {
    const performDelete = vi.fn()
    const { result, unmount } = renderHook(() => useUndoableDelete<string>())

    act(() => {
      result.current.scheduleDelete('1', 'Долг удалён', performDelete)
    })
    expect(performDelete).not.toHaveBeenCalled()

    unmount()

    expect(performDelete).toHaveBeenCalledTimes(1)
  })
})
