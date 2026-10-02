import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import useCountUp from './useCountUp'

describe('useCountUp', () => {
  afterEach(() => vi.restoreAllMocks())

  it('counts up to the target even when the rAF clock and performance.now() disagree', () => {
    // The rAF timestamp and performance.now() are not guaranteed to share a
    // time base. With the old implementation this showed negative values
    // (-55 for a target of 3) or stayed stuck at 0.
    vi.spyOn(performance, 'now').mockReturnValue(1_000_000)
    const callbacks = []
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      callbacks.push(cb)
      return callbacks.length
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})

    const { result } = renderHook(() => useCountUp(3, 600))
    const seen = []
    for (const ts of [0, 100, 300, 700]) {
      const cb = callbacks.shift()
      if (!cb) break
      act(() => cb(ts))
      seen.push(result.current)
    }

    expect(Math.min(...seen)).toBeGreaterThanOrEqual(0)
    expect(result.current).toBe(3)
  })

  it('never goes negative if a later frame reports an earlier timestamp', () => {
    const callbacks = []
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      callbacks.push(cb)
      return callbacks.length
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})

    const { result } = renderHook(() => useCountUp(10, 600))
    act(() => callbacks.shift()(500))
    act(() => callbacks.shift()(100))
    expect(result.current).toBeGreaterThanOrEqual(0)
  })
})
