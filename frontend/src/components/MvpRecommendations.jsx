import { IconAlertTriangle, IconLightbulb } from './icons'
import DegradedBanner from './DegradedBanner'
import Citation from './Citation'

const LEVEL_STYLES = {
  low:     'border-border-strong bg-panel text-muted-strong',
  medium:  'border-amber-400 bg-amber-100 text-amber-800',
  high:    'border-accent/40 bg-accent/10 text-accent',
  unknown: 'border-border-strong bg-panel text-muted-strong',
}

function Badge({ label, value }) {
  const level = LEVEL_STYLES[value] ? value : 'unknown'
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${LEVEL_STYLES[level]}`}>
      {label}: {level}
    </span>
  )
}

function priorityFor(impact, effort) {
  if (impact === 'high' && effort !== 'high') return 'P0'
  if (impact === 'high' || (impact === 'medium' && effort !== 'high')) return 'P1'
  return 'P2'
}

const PHASE_META = {
  P0: {
    label: 'P0 — Launch',
    sub: 'Ship on day one',
    dot: 'bg-accent',
    ring: 'border-accent/40 bg-accent/5',
    badge: 'bg-accent text-white',
    line: 'bg-accent/30',
  },
  P1: {
    label: 'P1 — Shortly after',
    sub: 'First 30–60 days',
    dot: 'bg-info',
    ring: 'border-info/30 bg-info/5',
    badge: 'border border-info/40 bg-info/10 text-info',
    line: 'bg-info/20',
  },
  P2: {
    label: 'P2 — Future',
    sub: 'Once you have signal',
    dot: 'bg-border-strong',
    ring: 'border-border-strong bg-surface',
    badge: 'border border-border-strong bg-panel text-muted-strong',
    line: 'bg-border',
  },
}

function FeatureCard({ item, meta, sourceMap }) {
  return (
    <article className={`rounded-xl border p-5 ${meta.ring}`}>
      <div className="flex items-start gap-2.5">
        <span className={`mt-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${meta.badge}`}>
          {item._priority}
        </span>
        <IconLightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <h3 className="font-serif text-base font-semibold leading-snug text-text">
          {item.feature}
          {sourceMap && <Citation sourceIds={item.sourceIds} sourceMap={sourceMap} />}
        </h3>
      </div>
      {item.rationale && (
        <p className="mt-3 text-sm leading-relaxed text-muted">{item.rationale}</p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Badge label="Impact" value={item.impact} />
        <Badge label="Effort" value={item.effort} />
      </div>
    </article>
  )
}

export default function MvpRecommendations({ data, error, sourceMap }) {
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

  // Tag each feature with its computed priority, then group
  const tagged = features.map((f) => ({ ...f, _priority: priorityFor(f.impact, f.effort) }))
  const phases = ['P0', 'P1', 'P2'].map((p) => ({
    key: p,
    meta: PHASE_META[p],
    items: tagged.filter((f) => f._priority === p),
  })).filter((ph) => ph.items.length > 0)

  return (
    <div>
      {data.degraded && <DegradedBanner />}

      {/* Phase legend */}
      <div className="mb-6 flex flex-wrap gap-3">
        {phases.map(({ key, meta }) => (
          <div key={key} className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{meta.label}</span>
          </div>
        ))}
      </div>

      {/* Phase groups */}
      <div className="space-y-8">
        {phases.map(({ key, meta, items }, pi) => (
          <div key={key} className="relative pl-6">
            {/* Vertical timeline line connecting phases */}
            {pi < phases.length - 1 && (
              <div className={`absolute left-[7px] top-8 h-full w-0.5 ${meta.line}`} />
            )}

            {/* Phase header with dot */}
            <div className="mb-4 flex items-center gap-3">
              <span className={`absolute left-0 h-3.5 w-3.5 rounded-full border-2 border-surface ${meta.dot}`} />
              <div>
                <p className="font-mono text-[11px] font-semibold uppercase tracking-widest text-text">{meta.label}</p>
                <p className="font-mono text-[9px] text-muted">{meta.sub}</p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {items.map((item, i) => (
                <FeatureCard key={i} item={item} meta={meta} sourceMap={sourceMap} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
