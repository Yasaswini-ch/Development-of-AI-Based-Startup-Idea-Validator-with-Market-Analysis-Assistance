import { IconAlertTriangle, IconLightbulb } from './icons'
import DegradedBanner from './DegradedBanner'

const LEVEL_STYLES = {
  low: 'border-border bg-panel text-muted',
  medium: 'border-amber-300 bg-amber-50 text-amber-700',
  high: 'border-accent/30 bg-accent/5 text-accent',
  unknown: 'border-border bg-panel text-muted',
}

function Badge({ label, value }) {
  const level = LEVEL_STYLES[value] ? value : 'unknown'
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${LEVEL_STYLES[level]}`}>
      {label}: {level}
    </span>
  )
}

export default function MvpRecommendations({ data, error }) {
  if (data === null || data === undefined) {
    return (
      <div className="flex flex-col items-center justify-center p-2 text-center">
        <IconAlertTriangle className="h-5 w-5 text-muted" />
        <p className="mt-2 text-sm font-medium text-text">MVP recommendations weren&apos;t available</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          {error || 'This analysis failed to complete for this request.'}
        </p>
      </div>
    )
  }

  const features = Array.isArray(data.features) ? data.features : []
  if (features.length === 0) {
    return <p className="text-center text-sm text-muted">No MVP features were recommended.</p>
  }

  return (
    <div>
      {data.degraded && <DegradedBanner />}
      <div className="grid gap-3 sm:grid-cols-2">
        {features.map((item, index) => (
          <article key={index} className="rounded-xl border border-border bg-surface p-5">
            <div className="flex items-start gap-2">
              <IconLightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <h3 className="text-sm font-semibold leading-snug text-text">{item.feature}</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted">{item.rationale}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge label="Impact" value={item.impact} />
              <Badge label="Effort" value={item.effort} />
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
