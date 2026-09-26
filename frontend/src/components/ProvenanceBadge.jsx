import { IconCheckCircle, IconInfo } from './icons'

// Pillar 1: Claim Provenance & Inference Badging (AFFINITY 5-pillar spec
// §4.1B). The backend already computes this exact {"status", "sourceCount"}
// shape per claim (see backend/agent/output_guard.py's provenance()) - this
// component only renders it, it never re-derives grounded/inferred itself,
// so the badge can never disagree with what verification.py actually kept.
//
// Also accepts a bare sourceIds array (older/cached shape, or a claim that
// doesn't carry a computed provenance field) and derives the same shape
// client-side, so callers never need an `if` before rendering this.
function toProvenance(provenance, sourceIds) {
  if (provenance && typeof provenance.status === 'string') return provenance
  const sourceCount = Array.isArray(sourceIds) ? sourceIds.length : 0
  return { status: sourceCount > 0 ? 'grounded' : 'inferred', sourceCount }
}

export default function ProvenanceBadge({ provenance, sourceIds, className = '' }) {
  const { status, sourceCount } = toProvenance(provenance, sourceIds)
  const grounded = status === 'grounded'

  const label = grounded
    ? `Backed by ${sourceCount} primary source${sourceCount === 1 ? '' : 's'}`
    : 'Synthesized via industry heuristics (no direct search match)'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide ${
        grounded
          ? 'border-success/40 bg-success/10 text-success'
          : 'border-amber-400/50 bg-amber-400/10 text-amber-600'
      } ${className}`}
      title={label}
    >
      {grounded ? <IconCheckCircle className="h-3 w-3" /> : <IconInfo className="h-3 w-3" />}
      {grounded ? 'Grounded' : 'Inferred'}
    </span>
  )
}
