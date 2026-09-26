// Headline go / no-go answer (backend/agent/verdict.py) - recombined from
// scores the report already shows, so this card only states the decision,
// why, and the one next step. Renders nothing when the backend had no
// market signal to base a verdict on.
const DECISION_STYLES = {
  pursue: { border: 'border-success/50', badge: 'border-success/40 bg-success/15 text-success' },
  validate_first: { border: 'border-accent/50', badge: 'border-accent/40 bg-accent/10 text-accent' },
  rethink: { border: 'border-danger/40', badge: 'border-danger/40 bg-danger/10 text-danger' },
}

export default function VerdictCard({ data }) {
  if (!data || !data.decision) return null
  const style = DECISION_STYLES[data.decision] || DECISION_STYLES.validate_first
  return (
    <section
      aria-label="Verdict"
      className={`rounded-2xl border-[1.5px] bg-panel p-6 shadow-sm sm:p-8 ${style.border}`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-text">Verdict</h2>
        <span
          className={`rounded-full border px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide ${style.badge}`}
        >
          {data.label}
        </span>
      </div>
      <p className="mt-3 font-serif text-lg leading-snug text-text">{data.headline}</p>
      {data.reasons?.length > 0 && (
        <ul className="mt-3 space-y-1">
          {data.reasons.map((reason, i) => (
            <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-muted-strong">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-border-strong" />
              {reason}
            </li>
          ))}
        </ul>
      )}
      {data.nextStep && (
        <p className="mt-4 border-t border-border pt-3 text-sm leading-relaxed text-text">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-wide text-accent">Next step </span>
          {data.nextStep}
        </p>
      )}
    </section>
  )
}
