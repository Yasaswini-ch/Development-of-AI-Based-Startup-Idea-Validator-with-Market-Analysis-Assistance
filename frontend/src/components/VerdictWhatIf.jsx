import { useState } from 'react'
import { DECISION_STYLES } from './VerdictCard'
import { PURSUE_AT, decide, factsFrom, score } from '../lib/whatIf'

const LABELS = { pursue: 'Pursue', validate_first: 'Validate first', rethink: 'Rethink' }

const SLIDERS = [
  ['demand', 'Market demand', 'Higher is better'],
  ['risk', 'Execution risk', 'Lower is better'],
  ['velocity', 'Growth velocity', 'Higher is better'],
]

// "What would change this verdict": the verdict is deterministic, so the three
// inputs behind the headline score can be moved here and the result recomputed
// in the browser - no model call, nothing saved. Not rendered for reports whose
// headline is not the market-viability score (no inputs to move).
export default function VerdictWhatIf({ verdict, marketViability, swot, assumptions, confidence, marketOpportunity }) {
  const base =
    marketViability && typeof marketViability.score === 'number'
      ? { demand: marketViability.marketDemand, risk: marketViability.executionRisk, velocity: marketViability.growthVelocity }
      : null
  const [vals, setVals] = useState(base)
  const [resolved, setResolved] = useState(false)
  if (!base || !vals || !verdict || verdict.scoreName !== 'Market viability' || Object.values(base).some((v) => typeof v !== 'number')) {
    return null
  }

  const facts = factsFrom({ swot, assumptions, confidence, marketOpportunity })
  const effective = resolved ? { ...facts, unmitigated: 0, unproven: 0 } : facts
  const next = score(vals)
  const decision = decide(next, effective)
  const style = DECISION_STYLES[decision] || DECISION_STYLES.validate_first
  const changed = decision !== verdict.decision || next !== verdict.score
  const canResolve = facts.unmitigated > 0 || facts.unproven > 0
  const gap = PURSUE_AT - next

  return (
    <section
      aria-label="What would change this verdict"
      className="rounded-2xl border border-border-strong bg-surface p-5"
      data-testid="verdict-whatif"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-strong">
          What would change this verdict
        </p>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${style.badge}`}
            data-testid="whatif-decision"
          >
            {LABELS[decision]}
          </span>
          <span className="font-serif text-xl text-text" data-testid="whatif-score">
            {next}
          </span>
          <span className="font-mono text-[10px] text-muted">/100</span>
        </div>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {SLIDERS.map(([key, label, hint]) => (
          <label key={key} className="block text-xs text-muted">
            <span className="flex justify-between">
              <span className="font-semibold text-text">{label}</span>
              <span>
                {vals[key]} <span className="text-muted/60">(was {base[key]})</span>
              </span>
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
      {canResolve && (
        <label className="mt-3 flex items-center gap-2 text-xs text-muted-strong">
          <input type="checkbox" checked={resolved} onChange={(e) => setResolved(e.target.checked)} />
          Assume the unmitigated risks and unproven assumptions are dealt with
        </label>
      )}
      <p className="mt-3 text-xs leading-relaxed text-muted">
        {changed
          ? decision === verdict.decision
            ? `Same call (${LABELS[decision]}), score moves from ${verdict.score} to ${next}.`
            : `This would change the call from ${verdict.label} to ${LABELS[decision]}.`
          : 'Move a slider to see what it would take.'}
        {effective.highRisks >= 3 ? ` ${effective.highRisks} high-severity risks force a Rethink whatever the score is; fewer than 3 are needed.` : ''}
        {decision !== 'pursue' && gap > 0 ? ` Pursue needs a score of ${PURSUE_AT} (${gap} more) and nothing unproven.` : ''} Only
        these three inputs and the open risks and assumptions feed the verdict; price and CAC do not.
      </p>
    </section>
  )
}
