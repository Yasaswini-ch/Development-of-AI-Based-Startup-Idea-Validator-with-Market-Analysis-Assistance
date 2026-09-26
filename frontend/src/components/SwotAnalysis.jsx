import { IconAlertTriangle, IconCheckCircle, IconShield, IconTrendingUp } from './icons'
import DegradedBanner from './DegradedBanner'
import Citation from './Citation'

const QUADRANTS = [
  {
    key: 'strengths',
    label: 'Strengths',
    sub: 'What you have going for you',
    Icon: IconCheckCircle,
    dot: 'bg-success',
    itemDot: 'bg-success',
  },
  {
    key: 'weaknesses',
    label: 'Weaknesses',
    sub: 'Gaps to address early',
    Icon: IconAlertTriangle,
    dot: 'bg-warning-bright',
    itemDot: 'bg-warning-bright',
  },
  {
    key: 'opportunities',
    label: 'Opportunities',
    sub: 'External tailwinds to ride',
    Icon: IconTrendingUp,
    dot: 'bg-info',
    itemDot: 'bg-info',
  },
  {
    key: 'threats',
    label: 'Threats',
    sub: 'Risks that could block growth',
    Icon: IconShield,
    dot: 'bg-danger',
    itemDot: 'bg-danger',
  },
]

const SEV = {
  low:     { label: 'Low',     style: 'bg-success/10 text-success border-success/30' },
  medium:  { label: 'Medium',  style: 'bg-warning/10 text-warning border-warning/40' },
  high:    { label: 'High',    style: 'bg-danger/10 text-danger border-danger/30' },
  unknown: { label: '—',       style: 'bg-panel text-muted-strong border-border-strong' },
}

function sev(val) { return SEV[val] ?? SEV.unknown }

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

export default function SwotAnalysis({ data, error, sourceMap }) {
  if (data === null || data === undefined) return <Unavailable error={error} />

  const risks = Array.isArray(data.risks) ? data.risks : []

  return (
    <div className="space-y-6">
      {data.degraded && <DegradedBanner />}

      {/* 2×2 SWOT matrix */}
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border-strong bg-border-strong">
        {QUADRANTS.map(({ key, label, sub, Icon, dot, itemDot }) => {
          const items = Array.isArray(data[key]) ? data[key] : []
          return (
            <div key={key} className="flex flex-col bg-surface p-5">
              {/* Quadrant header */}
              <div className="mb-4 flex items-center gap-2.5">
                <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
                <div>
                  <p className="font-mono text-[11px] font-semibold uppercase tracking-widest text-text">{label}</p>
                  <p className="font-mono text-[10.5px] text-muted">{sub}</p>
                </div>
              </div>

              {/* Items as mini-cards */}
              {items.length > 0 ? (
                <div className="flex flex-col gap-2">
                  {items.map((item, i) => {
                    const text = typeof item === 'string' ? item : item.text
                    return (
                      <div key={i} className="flex items-start gap-2.5 rounded-lg border border-white/60 bg-white/50 p-3 shadow-sm">
                        <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${itemDot}`} />
                        <span className="text-sm leading-relaxed text-text">
                          {text}
                          {typeof item !== 'string' && sourceMap && (
                            <Citation sourceIds={item.sourceIds} sourceMap={sourceMap} />
                          )}
                        </span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted">No {label.toLowerCase()} identified.</p>
              )}
            </div>
          )
        })}
      </div>

      {/* Risk register */}
      {risks.length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconAlertTriangle className="h-4 w-4 text-accent" />
            Risk register
          </h3>
          <div className="overflow-hidden rounded-2xl border border-border-strong">
            {/* Header row */}
            <div className="grid grid-cols-[1fr_auto_auto] gap-4 border-b border-border bg-surface px-5 py-2.5">
              <span className="font-mono text-[10.5px] uppercase tracking-widest text-muted">Risk</span>
              <span className="font-mono text-[10.5px] uppercase tracking-widest text-muted">Severity</span>
              <span className="font-mono text-[10.5px] uppercase tracking-widest text-muted">Likelihood</span>
            </div>
            {risks.map((item, i) => {
              const s = sev(item.severity)
              const l = sev(item.likelihood)
              return (
                <div
                  key={i}
                  className={`grid grid-cols-[1fr_auto_auto] items-center gap-4 px-5 py-4 ${
                    i < risks.length - 1 ? 'border-b border-border' : ''
                  }`}
                >
                  <p className="text-sm leading-relaxed text-text">
                    {item.risk}
                    {sourceMap && <Citation sourceIds={item.sourceIds} sourceMap={sourceMap} />}
                  </p>
                  <span className={`shrink-0 rounded-full border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wide ${s.style}`}>
                    {s.label}
                  </span>
                  <span className={`shrink-0 rounded-full border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wide ${l.style}`}>
                    {l.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
