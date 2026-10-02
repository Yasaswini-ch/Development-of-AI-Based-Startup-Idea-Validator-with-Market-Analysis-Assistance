import { IconAlertTriangle, IconTrendingUp } from './icons'
import Citation from './Citation'
import DegradedBanner from './DegradedBanner'

const FIT_STYLES = {
  high:   { badge: 'border-success/40 bg-success/10 text-success',   bar: 'bg-success',       label: 'HIGH FIT' },
  medium: { badge: 'border-accent/40 bg-accent/10 text-accent',      bar: 'bg-accent',        label: 'MEDIUM FIT' },
  low:    { badge: 'border-border-strong bg-panel text-muted-strong', bar: 'bg-border-strong', label: 'LOW FIT' },
}

function ModelCard({ model, sourceMap }) {
  const style = FIT_STYLES[model.fit] ?? FIT_STYLES.medium
  const companies = Array.isArray(model.exampleCompanies) ? model.exampleCompanies : []

  return (
    <div className="rounded-xl border border-border bg-surface">
      <div className={`h-1 w-full rounded-t-xl ${style.bar}`} />
      <div className="p-5">
        {/* header row */}
        <div className="mb-3 flex items-start justify-between gap-3">
          <h3 className="font-serif text-base font-semibold text-text">
            {model.name}
            {sourceMap && <Citation sourceIds={model.sourceIds} sourceMap={sourceMap} />}
          </h3>
          <span className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10.5px] font-bold uppercase tracking-wide ${style.badge}`}>
            {style.label}
          </span>
        </div>

        {/* pricing range badge */}
        {model.pricingRange && (
          <div className="mb-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] font-semibold text-text">
              <span className="text-accent">$</span>
              {model.pricingRange}
            </span>
          </div>
        )}

        {/* rationale */}
        {model.rationale && (
          <p className="text-sm leading-relaxed text-muted">{model.rationale}</p>
        )}

        {/* example companies */}
        {companies.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[10.5px] uppercase tracking-widest text-muted">Used by:</span>
            {companies.map((name, i) => (
              <span key={i} className="rounded border border-border bg-panel px-2 py-0.5 font-mono text-[10px] text-text">
                {name}
              </span>
            ))}
          </div>
        )}

        {/* tradeoffs */}
        {model.tradeoffs && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/25 bg-warning/5 px-3 py-2.5">
            <span className="mt-0.5 shrink-0 text-[11px] text-warning-bright">⚠</span>
            <p className="text-xs leading-relaxed text-warning">
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
    return <p className="text-center text-sm text-muted">{data.degraded ? "The AI step for revenue models did not run for this report, and no competitor pricing was found to infer from." : "No revenue models were suggested."}</p>
  }

  const highFitCount = models.filter((m) => m.fit === 'high').length

  return (
    <div>
      {data.degraded && <DegradedBanner />}
      <div className="mb-4 flex items-center gap-2.5">
        <IconTrendingUp className="h-4 w-4 shrink-0 text-accent" />
        <p className="text-sm text-muted">
          {highFitCount > 0
            ? <><span className="font-semibold text-accent">{highFitCount} model{highFitCount > 1 ? 's' : ''}</span> fit the evidence well — with pricing ranges and comparable companies</>
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
