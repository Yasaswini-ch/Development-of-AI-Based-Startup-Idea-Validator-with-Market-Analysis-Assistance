import { IconAlertTriangle, IconTrendingUp } from './icons'
import Citation from './Citation'
import DegradedBanner from './DegradedBanner'

const FIT_STYLES = {
  high:   { badge: 'border-success/40 bg-success/10 text-success',   bar: 'bg-success',   label: 'HIGH FIT' },
  medium: { badge: 'border-accent/40 bg-accent/10 text-accent',      bar: 'bg-accent',    label: 'MEDIUM FIT' },
  low:    { badge: 'border-border-strong bg-panel text-muted-strong', bar: 'bg-border-strong', label: 'LOW FIT' },
}

function ModelCard({ model, sourceMap }) {
  const style = FIT_STYLES[model.fit] ?? FIT_STYLES.medium
  return (
    <div className="rounded-xl border border-border bg-surface">
      <div className={`h-1 w-full rounded-t-xl ${style.bar}`} />
      <div className="p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="font-serif text-base font-semibold text-text">
            {model.name}
            {sourceMap && <Citation sourceIds={model.sourceIds} sourceMap={sourceMap} />}
          </h3>
          <span className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide ${style.badge}`}>
            {style.label}
          </span>
        </div>
        {model.rationale && (
          <p className="text-sm leading-relaxed text-muted">{model.rationale}</p>
        )}
        {model.tradeoffs && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
            <span className="mt-0.5 shrink-0 text-[11px] text-amber-500">⚠</span>
            <p className="text-xs leading-relaxed text-amber-800">
              <span className="font-semibold">Watch out:</span> {model.tradeoffs}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default function RevenueModels({ data, error, sourceMap }) {
  if (data === null || data === undefined) {
    return (
      <div className="flex flex-col items-center justify-center p-2 text-center">
        <IconAlertTriangle className="h-5 w-5 text-muted" />
        <p className="mt-2 text-sm font-medium text-text">Revenue model suggestions weren&apos;t available</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          {error || 'This analysis failed to complete for this request.'}
        </p>
      </div>
    )
  }

  const models = Array.isArray(data.models) ? data.models : []
  if (models.length === 0) {
    return <p className="text-center text-sm text-muted">No revenue models were suggested.</p>
  }

  const highFitCount = models.filter((m) => m.fit === 'high').length

  return (
    <div>
      {data.degraded && <DegradedBanner />}
      <div className="mb-4 flex items-center gap-2.5">
        <IconTrendingUp className="h-4 w-4 shrink-0 text-accent" />
        <p className="text-sm text-muted">
          {highFitCount > 0
            ? <><span className="font-semibold text-accent">{highFitCount} model{highFitCount > 1 ? 's' : ''}</span> fit the evidence well — ranked by fit with your market and customer profile</>
            : <>{models.length} monetization options ranked by fit with your specific market and customer profile</>
          }
        </p>
      </div>
      <div className="space-y-4">
        {models.map((model, i) => (
          <ModelCard key={i} model={model} sourceMap={sourceMap} />
        ))}
      </div>
    </div>
  )
}
