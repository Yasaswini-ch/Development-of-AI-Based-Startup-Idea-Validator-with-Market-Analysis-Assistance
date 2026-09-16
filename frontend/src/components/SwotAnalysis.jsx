import {
  IconAlertTriangle,
  IconCheckCircle,
  IconShield,
  IconTrendingUp,
} from './icons'
import DegradedBanner from './DegradedBanner'

const QUADRANTS = [
  {
    key: 'strengths',
    label: 'Strengths',
    Icon: IconCheckCircle,
    accent: 'border-accent/30 bg-accent/5',
  },
  {
    key: 'weaknesses',
    label: 'Weaknesses',
    Icon: IconAlertTriangle,
    accent: 'border-border bg-surface',
  },
  {
    key: 'opportunities',
    label: 'Opportunities',
    Icon: IconTrendingUp,
    accent: 'border-accent/30 bg-accent/5',
  },
  {
    key: 'threats',
    label: 'Threats',
    Icon: IconShield,
    accent: 'border-border bg-surface',
  },
]

const SEVERITY_STYLES = {
  low: 'border-accent/20 bg-accent/5 text-accent',
  medium: 'border-amber-300 bg-amber-50 text-amber-700',
  high: 'border-danger/30 bg-danger/5 text-danger',
  unknown: 'border-border bg-panel text-muted',
}

function Unavailable({ error }) {
  return (
    <div className="flex flex-col items-center justify-center p-2 text-center">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">SWOT and risk analysis wasn&apos;t available</p>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
        {error || 'This analysis failed to complete for this request.'}
      </p>
    </div>
  )
}

export default function SwotAnalysis({ data, error }) {
  if (data === null || data === undefined) return <Unavailable error={error} />

  const risks = Array.isArray(data.risks) ? data.risks : []

  return (
    <div className="space-y-6">
      {data.degraded && <DegradedBanner />}
      <div className="grid gap-3 sm:grid-cols-2">
        {QUADRANTS.map(({ key, label, Icon, accent }) => {
          const items = Array.isArray(data[key]) ? data[key] : []
          return (
            <section key={key} className={`rounded-xl border p-5 ${accent}`}>
              <h3 className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
                <Icon className="h-4 w-4 text-accent" />
                {label}
              </h3>
              {items.length > 0 ? (
                <ul className="mt-3 space-y-2">
                  {items.map((item, index) => (
                    <li key={index} className="flex gap-2 text-sm leading-relaxed text-text">
                      <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-muted">No {label.toLowerCase()} identified.</p>
              )}
            </section>
          )
        })}
      </div>

      <section>
        <h3 className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconAlertTriangle className="h-4 w-4 text-accent" />
          Key risks
        </h3>
        {risks.length > 0 ? (
          <div className="space-y-2">
            {risks.map((item, index) => {
              const severity = SEVERITY_STYLES[item.severity] ? item.severity : 'unknown'
              const likelihood = SEVERITY_STYLES[item.likelihood] ? item.likelihood : 'unknown'
              return (
                <div
                  key={index}
                  className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4 sm:flex-row sm:items-start sm:justify-between"
                >
                  <p className="text-sm leading-relaxed text-text">{item.risk}</p>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    <span className={`w-fit rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${SEVERITY_STYLES[severity]}`}>
                      Severity: {severity}
                    </span>
                    <span className={`w-fit rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${SEVERITY_STYLES[likelihood]}`}>
                      Likelihood: {likelihood}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-sm text-muted">No specific risks identified.</p>
        )}
      </section>
    </div>
  )
}
