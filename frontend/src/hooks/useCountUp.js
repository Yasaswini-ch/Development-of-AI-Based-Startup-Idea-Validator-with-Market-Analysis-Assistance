import { useEffect, useState } from 'react'

export default function useCountUp(target, durationMs = 600) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    let frame
    // Start the clock on the first animation frame rather than with
    // performance.now(): the rAF timestamp and performance.now() are not
    // guaranteed to share a time base (the rAF value can even precede it),
    // which made progress negative - a target of 3 briefly displayed -55 -
    // or stuck at 0 until the two clocks happened to line up.
    let start = null

    function tick(now) {
      if (start === null) start = now
      const progress = Math.max(0, Math.min(1, (now - start) / durationMs))
      setValue(Math.round(target * progress))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs])

  return value
}
