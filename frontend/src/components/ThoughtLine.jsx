import { useEffect, useRef, useState } from 'react'
import { IconCheck, IconChevronDown, IconSparkles } from './icons'
import './ThoughtLine.css'

// Adapted from React Bits' ThoughtLine: one breathing line with a live
// timer while the pipeline runs, and a trace of the steps reached so far
// underneath (the last step pulses, earlier ones tick). On settle the
// clock freezes into the sentence ("Validated in 42.3s") and the trace
// folds away.
//
// Differences from the original, to fit this app: no motion or Hugeicons
// dependency (the breath and shimmer are plain CSS keyframes, the glyphs
// come from icons.jsx), colours come from the theme tokens, and the props
// are trimmed to what the loading panel uses.

const fmt = (ds) => (ds < 600 ? `${(ds / 10).toFixed(1)}s` : `${Math.floor(ds / 600)}m ${((ds % 600) / 10).toFixed(1)}s`)

export default function ThoughtLine({
  label = 'Thinking…',
  doneLabel = 'Done in',
  steps = [],
  working = true,
  showTimer = true,
  collapsible = true,
  collapseOnSettle = true,
  onSettle,
  className = '',
}) {
  const timerRef = useRef(null)
  const elapsedRef = useRef(0)
  const onSettleRef = useRef(onSettle)
  const wasWorking = useRef(working)
  // A manual toggle only applies to the phase (working / settled) it was
  // made in, so settling still folds the trace even if it was opened by hand.
  const [toggled, setToggled] = useState({ working, open: null })
  const defaultOpen = working || !collapseOnSettle
  const open = toggled.working === working && toggled.open !== null ? toggled.open : defaultOpen
  const hasTrace = steps.length > 0
  const canToggle = collapsible && hasTrace

  useEffect(() => {
    onSettleRef.current = onSettle
  })

  // The clock writes straight to the DOM every 100ms instead of through
  // state, so the rest of the form doesn't re-render ten times a second.
  useEffect(() => {
    if (!working) return undefined
    const startedAt = performance.now()
    const paint = () => {
      const ds = Math.floor((performance.now() - startedAt) / 100)
      elapsedRef.current = ds
      if (timerRef.current) timerRef.current.textContent = fmt(ds)
    }
    paint()
    const id = setInterval(paint, 100)
    return () => clearInterval(id)
  }, [working])

  useEffect(() => {
    if (wasWorking.current && !working) onSettleRef.current?.(elapsedRef.current / 10)
    wasWorking.current = working
  }, [working])

  const head = (
    <>
      <span className="thought-line__glyph" aria-hidden="true">
        <IconSparkles />
      </span>
      <span key={working ? 'work' : 'done'} className="thought-line__label" data-shimmer={working ? '' : undefined}>
        {working ? label : doneLabel}
      </span>
      {showTimer && (
        <span ref={timerRef} className="thought-line__timer" aria-hidden="true">
          0.0s
        </span>
      )}
      {canToggle && (
        <span className="thought-line__chevron" aria-hidden="true">
          <IconChevronDown />
        </span>
      )}
    </>
  )

  return (
    <div
      className={`thought-line ${className}`}
      data-working={working ? '' : undefined}
      data-open={open && hasTrace ? '' : undefined}
    >
      <span className="sr-only" role="status">
        {working ? steps[steps.length - 1] || label : doneLabel}
      </span>
      {canToggle ? (
        <button
          type="button"
          className="thought-line__head"
          aria-expanded={open}
          onClick={() => setToggled({ working, open: !open })}
        >
          {head}
        </button>
      ) : (
        <div className="thought-line__head">{head}</div>
      )}
      {hasTrace && (
        <div className="thought-line__trace" data-open={open ? '' : undefined} aria-hidden={!open}>
          <div className="thought-line__fold">
            <ol className="thought-line__steps">
              {steps.map((text, i) => {
                const done = !working || i < steps.length - 1
                return (
                  <li key={text} className="thought-line__step" data-done={done ? '' : undefined}>
                    <span className="thought-line__mark" aria-hidden="true">
                      {done ? <IconCheck /> : <i className="thought-line__pulse" />}
                    </span>
                    {text}
                  </li>
                )
              })}
            </ol>
          </div>
        </div>
      )}
    </div>
  )
}
