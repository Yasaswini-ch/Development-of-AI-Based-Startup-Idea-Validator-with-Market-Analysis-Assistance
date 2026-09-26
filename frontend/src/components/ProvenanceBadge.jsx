import { IconCheckCircle, IconInfo } from './icons'

// The app's one evidence scale (Pillar 1, AFFINITY 5-pillar spec §4.1B),
// used for every "how sure are we" signal so a founder only has to learn
// one legend:
//   grounded - backed by at least one cited source
//   partial  - some of the chain is sourced, some estimated (wedge
//              conviction, see StrategicWedgeCard.jsx)
//   inferred - synthesized from heuristics, no direct search match
//
// The backend already computes {"status", "sourceCount"} per claim (see
// backend/agent/output_guard.py's provenance()) - this component only
// renders it, so the badge can never disagree with what verification.py
// kept. A bare sourceIds array (older/cached shape) derives the same
// grounded/inferred split client-side.
function toProvenance(provenance, sourceIds) {
  if (provenance && typeof provenance.status === 'string') return provenance
  const sourceCount = Array.isArray(sourceIds) ? sourceIds.length : 0
  return { status: sourceCount > 0 ? 'grounded' : 'inferred', sourceCount }
}

const STATUS = {
  grounded: {
    text: 'Grounded',
    style: 'border-success/40 bg-success/10 text-success',
    Icon: IconCheckCircle,
  },
  partial: {
    text: 'Partly grounded',
    style: 'border-warning/40 bg-warning/10 text-warning',
    Icon: IconInfo,
  },
  inferred: {
    text: 'Inferred',
    style: 'border-border-strong bg-surface text-muted-strong',
    Icon: IconInfo,
  },
}

function describe(status, sourceCount, title) {
  if (title) return title
  if (status === 'grounded') {
    return `Backed by ${sourceCount} primary source${sourceCount === 1 ? '' : 's'}`
  }
  if (status === 'partial') return 'Partly backed by sources, partly estimated'
  return 'Synthesized via industry heuristics (no direct search match)'
}

export default function ProvenanceBadge({ provenance, sourceIds, status: statusOverride, label, title, className = '' }) {
  const computed = toProvenance(provenance, sourceIds)
  const status = STATUS[statusOverride] ? statusOverride : STATUS[computed.status] ? computed.status : 'inferred'
  const { text, style, Icon } = STATUS[status]
  const description = describe(status, computed.sourceCount, title)

  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 align-middle font-mono text-[10.5px] uppercase tracking-wide ${style} ${className}`}
      title={description}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label || text}
    </span>
  )
}
