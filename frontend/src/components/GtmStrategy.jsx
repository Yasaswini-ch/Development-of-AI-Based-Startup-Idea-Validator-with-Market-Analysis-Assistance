import { IconAlertTriangle, IconGlobe, IconTrendingUp, IconUsers } from './icons'
import DegradedBanner from './DegradedBanner'
import Citation from './Citation'
import GtmCommercialModel from './GtmCommercialModel'
import { roadmapWeekRanges } from '../lib/timeline'

// Default launch windows when there's no delivery roadmap to align with
// (older sessions, or the MVP section failed).
const DEFAULT_TIMESPANS = ['Weeks 1 – 4', 'Month 2 – 3', 'Month 4+']

// Launch windows on the same week axis as the Delivery Roadmap: Foundation
// runs alongside the Alpha, Traction alongside the closed Beta, and Scale
// starts at GA.
function launchTimespans(roadmap) {
  const ranges = roadmapWeekRanges(roadmap)
  if (ranges.length < 3) return DEFAULT_TIMESPANS
  return [ranges[0].label, ranges[1].label, `Week ${ranges[2].start} onward`]
}

// Derives a 3-phase launch timeline from the existing GTM fields the backend
// already returns (positioning, channels, earlyCustomerApproach) — no new
// backend data needed. Channels are split across phases so they feel
// sequenced rather than dumped as a flat list.
function buildPhases(data, timespans = DEFAULT_TIMESPANS) {
  const channels = Array.isArray(data.channels) ? data.channels : []
  const mid = Math.ceil(channels.length / 2)
  const phase1Ch = channels.slice(0, mid)
  const phase2Ch = channels.slice(mid)

  return [
    {
      label: 'Foundation',
      timespan: timespans[0],
      color: { dot: 'bg-accent', line: 'bg-accent/30', border: 'border-accent/30 bg-accent/5', badge: 'bg-accent text-white' },
      sections: [
        data.earlyCustomerApproach && {
          icon: IconUsers,
          heading: 'First customers',
          body: data.earlyCustomerApproach,
          sourceIds: data.earlyCustomerApproachSourceIds,
        },
        data.positioning && {
          icon: IconTrendingUp,
          heading: 'Positioning',
          body: data.positioning,
          sourceIds: data.positioningSourceIds,
        },
      ].filter(Boolean),
    },
    {
      label: 'Traction',
      timespan: timespans[1],
      color: { dot: 'bg-info', line: 'bg-info/20', border: 'border-info/30 bg-info/5', badge: 'border border-info/40 bg-info/10 text-info' },
      sections: [
        phase1Ch.length > 0 && {
          icon: IconGlobe,
          heading: 'Priority channels',
          channels: phase1Ch,
        },
      ].filter(Boolean),
    },
    ...(phase2Ch.length > 0 ? [{
      label: 'Scale',
      timespan: timespans[2],
      color: { dot: 'bg-success', line: null, border: 'border-success/30 bg-success/5', badge: 'border border-success/40 bg-success/10 text-success' },
      sections: [
        {
          icon: IconGlobe,
          heading: 'Expand channels',
          channels: phase2Ch,
        },
      ],
    }] : []),
  ]
}

const FIT_STYLES = {
  high:   'bg-success/10 text-success border-success/30',
  medium: 'bg-panel text-muted-strong border-border-strong',
  low:    'bg-border text-muted-strong border-border-strong',
}

function ChannelCard({ ch, sourceMap }) {
  const text = typeof ch === 'string' ? ch : ch.text
  const tactics = Array.isArray(ch.tactics) ? ch.tactics : []
  const fitScore = ch.fitScore
  const sourceIds = typeof ch !== 'string' ? ch.sourceIds : undefined

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium leading-snug text-text">
          {text}
          {sourceMap && <Citation sourceIds={sourceIds} sourceMap={sourceMap} />}
        </p>
        {fitScore && (
          <span className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${FIT_STYLES[fitScore] ?? FIT_STYLES.medium}`}>
            {fitScore} fit
          </span>
        )}
      </div>
      {tactics.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
          {tactics.map((t, i) => (
            <li key={i} className="flex items-start gap-2 text-xs leading-relaxed text-muted">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent/50" />
              {t}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function PhaseSection({ section, sourceMap }) {
  const Icon = section.icon
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">
        <Icon className="h-3.5 w-3.5" />
        {section.heading}
      </p>
      {section.body && (
        <p className="text-sm leading-relaxed text-text">
          {section.body}
          {sourceMap && <Citation sourceIds={section.sourceIds} sourceMap={sourceMap} />}
        </p>
      )}
      {section.channels && (
        <div className="space-y-2">
          {section.channels.map((ch, i) => (
            <ChannelCard key={i} ch={ch} sourceMap={sourceMap} />
          ))}
        </div>
      )}
    </div>
  )
}

function Targets({ data }) {
  const cac = data.acquisition?.estimatedCac
  const method = data.acquisition?.primaryMethod
  const kpis = Array.isArray(data.kpis) ? data.kpis : []
  if (!cac && !method && kpis.length === 0) return null
  return (
    <div className="mt-2 rounded-xl border border-border bg-surface p-5" data-testid="gtm-targets">
      <p className="mb-3 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">
        <IconTrendingUp className="h-3.5 w-3.5" />
        Acquisition cost and KPI targets
        <span className="rounded-full border border-border-strong px-1.5 py-0.5 normal-case tracking-normal">Estimate</span>
      </p>
      {(method || cac) && (
        <div className="mb-4">
          {cac && (
            <p className="text-sm text-text">
              Estimated CAC <span className="font-semibold">${Math.round(cac.low).toLocaleString()} – ${Math.round(cac.high).toLocaleString()}</span> per paying customer
            </p>
          )}
          {method && <p className="mt-1 text-sm leading-relaxed text-text">{method}</p>}
          {cac?.basis && <p className="mt-1 text-xs leading-relaxed text-muted">{cac.basis}</p>}
        </div>
      )}
      {kpis.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2">
          {kpis.map((k, i) => (
            <li key={i} className="rounded-lg border border-border bg-panel p-3">
              <p className="text-xs text-muted">{k.name}</p>
              <p className="mt-0.5 text-sm font-semibold text-text">{k.target}</p>
              {k.timeframe && <p className="font-mono text-[10px] text-muted">{k.timeframe}</p>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[11px] text-muted">Model estimates from typical channel costs, not measured figures. Validate them in a pilot.</p>
    </div>
  )
}

export default function GtmStrategy({ data, error, sourceMap, roadmap }) {
  if (data === null || data === undefined) {
    return (
      <div className="flex flex-col items-center justify-center p-2 text-center">
        <IconAlertTriangle className="h-5 w-5 text-muted" />
        <p className="mt-2 text-sm font-medium text-text">Go-to-market strategy wasn&apos;t available</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          {error || 'This analysis failed to complete for this request.'}
        </p>
      </div>
    )
  }

  const phases = buildPhases(data, launchTimespans(roadmap))

  // Fallback: if none of the structured fields exist (e.g. older backend
  // response that only has a `strategy` string), just render that prose.
  const hasStructured = data.positioning || data.earlyCustomerApproach ||
    (Array.isArray(data.channels) && data.channels.length > 0)

  if (!hasStructured) {
    return (
      <p className="text-sm leading-relaxed text-text">
        {data.strategy || 'No go-to-market strategy was generated.'}
      </p>
    )
  }

  return (
    <div>
      {data.degraded && <DegradedBanner />}

      <div className="relative space-y-0">
        {phases.map((phase, pi) => {
          const { color } = phase
          const isLast = pi === phases.length - 1
          return (
            <div key={phase.label} className="relative pl-8">
              {/* Connecting line to next phase */}
              {!isLast && (
                <div className={`absolute left-[9px] top-5 h-full w-0.5 ${color.line}`} />
              )}

              {/* Phase dot */}
              <span className={`absolute left-0 top-1 h-4 w-4 rounded-full border-2 border-surface ${color.dot}`} />

              {/* Phase card */}
              <div className={`mb-6 rounded-xl border p-5 ${color.border}`}>
                {/* Header */}
                <div className="mb-4 flex items-center gap-3">
                  <span className={`rounded-full px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wide ${color.badge}`}>
                    {phase.label}
                  </span>
                  <span className="font-mono text-[10px] text-muted">{phase.timespan}</span>
                </div>

                {/* Sections within this phase */}
                <div className="space-y-5">
                  {phase.sections.map((section, si) => (
                    <PhaseSection key={si} section={section} sourceMap={sourceMap} />
                  ))}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <Targets data={data} />

      <GtmCommercialModel data={data.commercialModel} />
    </div>
  )
}
