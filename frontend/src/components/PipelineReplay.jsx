import { useState } from 'react'

// Friendly names for the pipeline's step ids (backend/agent/graph.py node names).
const LABELS = {
  web_search: 'Web research',
  confidence_indicator: 'Source agreement',
  market_opportunity: 'Market analysis',
  competitor_discovery: 'Competitor discovery',
  white_space: 'White-space map',
  swot_analysis: 'SWOT and risks',
  viability_score: 'Viability score',
  mvp_recommendation: 'MVP plan',
  gtm_strategy: 'Go-to-market',
  contradiction_detector: 'Contradiction check',
  experiment_generator: 'Experiments',
  action_plan: 'Action plan',
  assumption_tracker: 'Assumptions',
  revenue_models: 'Revenue models',
  confidence_dashboard: 'Evidence confidence',
  validation_sprint: 'Validation sprint',
  verdict: 'Verdict',
}

export function labelFor(node) {
  return LABELS[node] || String(node || '').replace(/_/g, ' ')
}

function shortModel(model) {
  return String(model).replace(/^(groq|gemini)\//, '').replace(/^openai\//, '')
}

// "How this report was made": each step the pipeline ran, how long it took and
// which model served it (steps without a model are plain code - search or
// scoring - not a language-model call). Rendered only for reports that carry a
// trace; older saved ones simply do not show it.
export default function PipelineReplay({ trace }) {
  const [open, setOpen] = useState(false)
  const steps = Array.isArray(trace) ? trace.filter((s) => s && s.node) : []
  if (steps.length === 0) return null
  const total = steps.reduce((n, s) => n + (Number(s.seconds) || 0), 0)
  const slowest = Math.max(...steps.map((s) => Number(s.seconds) || 0), 0.01)
  const models = new Set(steps.flatMap((s) => s.models || []))

  return (
    <div className="rounded-xl border border-border-strong bg-surface p-4" data-testid="pipeline-replay">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-strong">How this report was made</p>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="font-mono text-[10px] uppercase tracking-wide text-accent hover:text-accent-hover"
        >
          {open ? 'Hide steps' : 'Show steps'}
        </button>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text">
        <span className="font-semibold">{steps.length}</span> steps, <span className="font-semibold">{models.size}</span> model
        {models.size === 1 ? '' : 's'}, about <span className="font-semibold">{Math.round(total)}s</span> of processing in total (steps
        that ran side by side add up to more than the wall-clock time).
      </p>
      {open && (
        <ol className="mt-3 space-y-1.5 border-t border-border pt-3">
          {steps.map((s, i) => {
            const seconds = Number(s.seconds) || 0
            return (
              <li key={`${s.node}-${i}`} className="text-xs">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-semibold text-text">{labelFor(s.node)}</span>
                  <span className="shrink-0 font-mono text-[10px] text-muted">
                    {(s.models || []).length > 0 ? (s.models || []).map(shortModel).join(', ') : 'code only'} · {seconds.toFixed(1)}s
                  </span>
                </div>
                <div className="mt-1 h-1 overflow-hidden rounded-full bg-border">
                  <div className="h-full rounded-full bg-accent/60" style={{ width: `${Math.max(2, (seconds / slowest) * 100)}%` }} />
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
