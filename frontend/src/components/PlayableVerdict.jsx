import { useState } from 'react'
import { DECISION_STYLES } from './VerdictCard'
import { decide, score } from '../lib/whatIf'

const LABELS = { pursue: 'Pursue', validate_first: 'Validate first', rethink: 'Rethink' }
const START = { demand: 58, risk: 55, velocity: 52 }

const SLIDERS = [
  ['demand', 'Market demand', 'Higher is better'],
  ['risk', 'Execution risk', 'Lower is better'],
  ['velocity', 'Growth velocity', 'Higher is better'],
]

// The same scoring the real report uses (lib/whatIf.js mirrors the backend),
// on invented starting numbers, so a visitor can feel how the verdict moves
// before signing up. Nothing here is a real idea's result.
export default function PlayableVerdict() {
  const [vals, setVals] = useState(START)
  const value = score(vals)
  const decision = decide(value, {})
  const style = DECISION_STYLES[decision]

  return (
    <section className="mt-16" data-testid="playable-verdict">
      <p className="mb-2 text-center font-mono text-sm font-semibold uppercase tracking-[0.2em] text-accent">Try the verdict</p>
      <h2 className="mb-2 text-center font-serif text-3xl font-semibold text-text sm:text-4xl">The call is arithmetic you can see.</h2>
      <p className="mx-auto mb-6 max-w-xl text-center text-sm leading-relaxed text-muted">
        Demand, risk and growth set one score, and fixed rules turn it into Pursue, Validate first or Rethink. Drag them and watch it
        change. In your report these come from your own research.
      </p>
      <div className={`mx-auto max-w-2xl rounded-2xl border-[1.5px] bg-panel p-6 ${style.border}`}>
        <div className="flex items-center justify-between gap-3">
          <span
            className={`rounded-full border px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide ${style.badge}`}
            data-testid="playable-decision"
          >
            {LABELS[decision]}
          </span>
          <p className="font-serif text-4xl leading-none text-text">
            <span data-testid="playable-score">{value}</span>
            <span className="ml-0.5 font-mono text-xs text-muted">/100</span>
          </p>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {SLIDERS.map(([key, label, hint]) => (
            <label key={key} className="block text-xs text-muted">
              <span className="flex justify-between">
                <span className="font-semibold text-text">{label}</span>
                <span>{vals[key]}</span>
              </span>
              <input
                type="range"
                min="0"
                max="100"
                value={vals[key]}
                aria-label={label}
                onChange={(e) => setVals({ ...vals, [key]: Number(e.target.value) })}
                className="mt-1 w-full"
              />
              <span className="text-[10px]">{hint}</span>
            </label>
          ))}
        </div>
        <p className="mt-4 text-center font-mono text-[10px] uppercase tracking-wide text-muted">
          Illustrative numbers. Pursue needs 65 or more and nothing unproven; below 40 is Rethink.
        </p>
      </div>
    </section>
  )
}
