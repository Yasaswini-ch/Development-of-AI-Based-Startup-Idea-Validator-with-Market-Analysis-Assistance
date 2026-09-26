import { IconAlertTriangle, IconShield } from './icons'
import Citation from './Citation'

// Bear case is derived from SWOT threats + risks — no backend agent needed.
// Frames the most serious investor objections the founder should preempt.

const SEVERITY_STYLES = {
  high:    { border: 'border-danger/40',    bg: 'bg-danger/5',    dot: 'bg-danger',        badge: 'border-danger/40 bg-danger/10 text-danger' },
  medium:  { border: 'border-warning/40', bg: 'bg-warning/5',    dot: 'bg-warning-bright',     badge: 'border-warning/40 bg-warning/5 text-warning' },
  low:     { border: 'border-border',       bg: 'bg-surface',     dot: 'bg-border-strong', badge: 'border-border-strong bg-panel text-muted-strong' },
  unknown: { border: 'border-border',       bg: 'bg-surface',     dot: 'bg-border-strong', badge: 'border-border-strong bg-panel text-muted-strong' },
}

function BearCard({ heading, mitigation, severity, sourceIds, sourceMap, index }) {
  const style = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.unknown
  return (
    <div className={`rounded-xl border p-5 ${style.border} ${style.bg}`}>
      <div className="flex items-start gap-3">
        <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} />
        <div className="min-w-0 flex-1">
          {/* header */}
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <p className="font-mono text-[10.5px] uppercase tracking-widest text-muted">
              Objection #{index + 1}
            </p>
            {severity && severity !== 'unknown' && (
              <span className={`rounded-full border px-2 py-0.5 font-mono text-[10.5px] font-bold uppercase tracking-wide ${style.badge}`}>
                {severity} severity
              </span>
            )}
          </div>

          {/* objection */}
          <p className="text-sm font-medium leading-snug text-text">
            {heading}
            {sourceMap && <Citation sourceIds={sourceIds} sourceMap={sourceMap} />}
          </p>

          {/* mitigation / your answer */}
          {mitigation && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 px-3 py-2.5">
              <span className="mt-0.5 shrink-0 text-[11px] text-success">✓</span>
              <p className="text-xs leading-relaxed text-success/80">
                <span className="font-semibold text-success">Your answer:</span>{' '}
                {mitigation}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function deriveCards(swot) {
  if (!swot) return []
  const cards = []

  // Risks with severity come first — they have structured severity/likelihood + optional mitigation
  const risks = Array.isArray(swot.risks) ? swot.risks : []
  for (const risk of risks.slice(0, 3)) {
    const text = typeof risk === 'string' ? risk : (risk.risk || '')
    if (!text || text.toLowerCase().includes('unavailable')) continue
    cards.push({
      heading: text,
      mitigation: typeof risk === 'object' ? (risk.mitigation || null) : null,
      severity: (typeof risk === 'object' && risk.severity) || 'unknown',
      sourceIds: (typeof risk === 'object' && risk.sourceIds) || [],
    })
  }

  // Fill remainder with raw threats (no mitigation available)
  const threats = Array.isArray(swot.threats) ? swot.threats : []
  for (const threat of threats) {
    if (cards.length >= 4) break
    const text = typeof threat === 'string' ? threat : (threat.text || '')
    if (!text) continue
    if (cards.some((c) => c.heading === text)) continue
    cards.push({
      heading: text,
      mitigation: null,
      severity: 'unknown',
      sourceIds: (typeof threat === 'object' && threat.sourceIds) || [],
    })
  }

  return cards.slice(0, 4)
}

export default function BearCase({ swot, sourceMap }) {
  const cards = deriveCards(swot)

  if (cards.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-2 text-center">
        <IconShield className="h-5 w-5 text-muted" />
        <p className="mt-2 text-sm font-medium text-text">No bear-case data available</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          Risks and threats are derived from the SWOT analysis. Run a full validation to see investor objections here.
        </p>
      </div>
    )
  }

  const withAnswer = cards.filter((c) => c.mitigation).length
  const highSeverityCount = cards.filter((c) => c.severity === 'high').length

  return (
    <div>
      <div className="mb-4 flex items-start gap-2.5">
        <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-bright" />
        <p className="text-sm text-muted">
          {highSeverityCount > 0
            ? <><span className="font-semibold text-text">The hardest questions an investor will ask.</span>{' '}
                {withAnswer > 0 && <>{withAnswer} include a suggested answer.</>}
              </>
            : <><span className="font-semibold text-text">Investor objections derived from your risk and threat profile.</span> Address these proactively in your pitch.</>
          }
        </p>
      </div>
      <div className="space-y-3">
        {cards.map((card, i) => (
          <BearCard
            key={i}
            index={i}
            heading={card.heading}
            mitigation={card.mitigation}
            severity={card.severity}
            sourceIds={card.sourceIds}
            sourceMap={sourceMap}
          />
        ))}
      </div>
    </div>
  )
}
