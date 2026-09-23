import { IconAlertTriangle, IconFlask, IconShield } from './icons'
import Citation from './Citation'

const UNCERTAINTY_STYLES = {
  high:   { bar: 'bg-danger',        badge: 'border-danger/40 bg-danger/10 text-danger',          label: 'HIGH' },
  medium: { bar: 'bg-amber-400',     badge: 'border-amber-400/50 bg-amber-50 text-amber-700',     label: 'MEDIUM' },
  low:    { bar: 'bg-success',       badge: 'border-success/40 bg-success/10 text-success',        label: 'LOW' },
}

const CATEGORY_LABELS = {
  demand:       'Demand',
  market:       'Market',
  technical:    'Technical',
  competitive:  'Competitive',
  regulatory:   'Regulatory',
}

function AssumptionCard({ item, index, sourceMap }) {
  const style = UNCERTAINTY_STYLES[item.uncertainty] ?? UNCERTAINTY_STYLES.medium
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-surface">
      {/* left accent bar */}
      <div className={`absolute left-0 top-0 h-full w-1 ${style.bar}`} />
      <div className="px-5 py-4 pl-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-panel font-mono text-[10px] font-bold text-muted">
            {index + 1}
          </span>
          <div className="min-w-0 flex-1">
            {/* badges */}
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide ${style.badge}`}>
                {style.label} uncertainty
              </span>
              {item.category && (
                <span className="rounded-full border border-border bg-panel px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted">
                  {CATEGORY_LABELS[item.category] ?? item.category}
                </span>
              )}
              {item.timeToValidate && (
                <span className="rounded-full border border-accent/30 bg-accent/5 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-accent">
                  ⏱ {item.timeToValidate}
                </span>
              )}
            </div>

            {/* assumption statement */}
            <p className="text-sm font-medium leading-snug text-text">
              {item.assumption}
              {sourceMap && <Citation sourceIds={item.sourceIds} sourceMap={sourceMap} />}
            </p>

            {/* risk if wrong */}
            {item.riskIfWrong && (
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2.5">
                <span className="mt-0.5 shrink-0 text-[11px] text-danger">✕</span>
                <p className="text-xs leading-relaxed text-danger/80">
                  <span className="font-semibold text-danger">If wrong:</span>{' '}
                  {item.riskIfWrong}
                </p>
              </div>
            )}

            {/* how to validate */}
            {item.howToValidate && (
              <div className="mt-2 flex items-start gap-2 rounded-lg border border-border bg-panel px-3 py-2.5">
                <IconFlask className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                <p className="text-xs leading-relaxed text-muted">
                  <span className="font-semibold text-text">Validate by:</span>{' '}
                  {item.howToValidate}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AssumptionTracker({ data, error, sourceMap }) {
  if (data === null || data === undefined) {
    return (
      <div className="flex flex-col items-center justify-center p-2 text-center">
        <IconAlertTriangle className="h-5 w-5 text-muted" />
        <p className="mt-2 text-sm font-medium text-text">Assumption analysis wasn&apos;t available</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          {error || 'This analysis failed to complete for this request.'}
        </p>
      </div>
    )
  }

  const assumptions = Array.isArray(data.assumptions) ? data.assumptions : []
  if (assumptions.length === 0) {
    return <p className="text-center text-sm text-muted">No key assumptions were identified.</p>
  }

  const highCount = assumptions.filter((a) => a.uncertainty === 'high').length

  return (
    <div>
      <div className="mb-4 flex items-center gap-2.5">
        <IconShield className="h-4 w-4 shrink-0 text-danger" />
        <p className="text-sm text-muted">
          {highCount > 0
            ? <><span className="font-semibold text-danger">{highCount} high-uncertainty bet{highCount > 1 ? 's' : ''}</span> you should validate first</>
            : <>{assumptions.length} assumptions ranked by uncertainty — validate the top ones before building</>
          }
        </p>
      </div>
      <div className="space-y-3">
        {assumptions.map((item, i) => (
          <AssumptionCard key={i} item={item} index={i} sourceMap={sourceMap} />
        ))}
      </div>
    </div>
  )
}
