import { useEffect, useState } from 'react'

// The pipeline's real step order (backend/agent/graph.py). `kind` is only set
// where it is certain: "code" steps are plain computation (search, formulas,
// rules), "model" steps are a language-model call. Others carry no tag rather
// than a guess. No timings here - those belong to real runs, which show them
// in the report's own "How this report was made" card.
export const STEPS = [
  { id: 'search', label: 'Web research', kind: 'code' },
  { id: 'agree', label: 'Source agreement', kind: 'code' },
  { id: 'market', label: 'Market analysis', kind: 'model' },
  { id: 'competitors', label: 'Competitor discovery', kind: 'model' },
  { id: 'whitespace', label: 'White-space map' },
  { id: 'swot', label: 'SWOT and risks', kind: 'model' },
  { id: 'viability', label: 'Viability score', kind: 'code' },
  { id: 'mvp', label: 'MVP plan', kind: 'model', lane: 'a' },
  { id: 'gtm', label: 'Go-to-market', kind: 'model', lane: 'b' },
  { id: 'contradictions', label: 'Contradiction check' },
  { id: 'experiments', label: 'Experiments' },
  { id: 'action', label: 'Action plan' },
  { id: 'assumptions', label: 'Assumptions', kind: 'model' },
  { id: 'revenue', label: 'Revenue models', kind: 'model' },
  { id: 'confidence', label: 'Evidence confidence', kind: 'code' },
  { id: 'sprint', label: 'Validation sprint', kind: 'code' },
  { id: 'verdict', label: 'Verdict', kind: 'code' },
]

const TAG = { code: 'code', model: 'model' }

export default function PipelineShowcase() {
  const [lit, setLit] = useState(0)

  useEffect(() => {
    const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setLit(STEPS.length)
      return undefined
    }
    const timer = setInterval(() => {
      setLit((n) => (n >= STEPS.length + 3 ? 0 : n + 1))
    }, 650)
    return () => clearInterval(timer)
  }, [])

  return (
    <section className="mt-16" data-testid="pipeline-showcase">
      <p className="mb-2 text-center font-mono text-sm font-semibold uppercase tracking-[0.2em] text-accent">Watch it work</p>
      <h2 className="mb-2 text-center font-serif text-3xl font-semibold text-text sm:text-4xl">Seventeen steps, not one chat reply.</h2>
      <p className="mx-auto mb-6 max-w-xl text-center text-sm leading-relaxed text-muted">
        Each step runs on its own and hands its result to the next, and a failed section is reported instead of hidden. Some steps are language-model
        calls; others are plain code (search, formulas, rules), which cannot make things up.
      </p>
      <ol className="grid gap-2 rounded-2xl border border-border bg-panel p-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => {
          const on = i < lit
          return (
            <li
              key={s.id}
              data-lit={on ? 'true' : 'false'}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors duration-300 ${
                on ? 'border-accent/50 bg-accent/10 text-text' : 'border-border bg-surface text-muted'
              }`}
            >
              <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] ${on ? 'bg-accent text-white' : 'bg-border text-muted'}`}>
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 leading-snug">{s.label}</span>
              {s.kind && (
                <span className="shrink-0 rounded-full border border-border-strong px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted">
                  {TAG[s.kind]}
                </span>
              )}
            </li>
          )
        })}
      </ol>
      <p className="mt-2 text-center font-mono text-[10px] uppercase tracking-wide text-muted">
        MVP plan and go-to-market run side by side. Real timings and models appear in every report.
      </p>
    </section>
  )
}
