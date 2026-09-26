import { useState } from 'react'
import { IconChevronDown, IconLightbulb } from './icons'
import ProvenanceBadge from './ProvenanceBadge'

// Pillar 4: 5-Vector Strategic Wedge Blueprint (AFFINITY 5-pillar spec
// §4.4). Renders whiteSpace.blueprints - computed deterministically by
// backend/agent/strategic_wedge.py - as an expandable Friction -> Blindspot
// -> Tailwind -> Wedge -> Moat chain, alongside (not replacing) the
// existing opportunity cards above.
//
// The collapsed card already says the point (the wedge itself and its key
// risk), so three cards don't read as identical headers. Conviction is
// shown on the app's shared evidence scale (ProvenanceBadge) with the
// percentage as secondary text.

const _VECTORS = [
  { key: 'observedFriction', label: 'Observed Friction' },
  { key: 'incumbentBlindspot', label: 'Incumbent Blindspot' },
  { key: 'structuralTailwind', label: 'Structural Tailwind' },
  { key: 'asymmetricWedge', label: 'Asymmetric Wedge' },
  { key: 'defensibilityMoat', label: 'Defensibility Moat' },
]

// convictionPercent is the share of the 4 evidence-based vectors that are
// actually grounded (0/25/50/75/100) - mapped onto grounded/partial/inferred.
function convictionStatus(percent) {
  if (percent >= 75) return 'grounded'
  if (percent >= 50) return 'partial'
  return 'inferred'
}

function VectorStep({ label, text, isLast }) {
  return (
    <div className="relative pl-6">
      {!isLast && <div className="absolute left-[5px] top-4 h-full w-0.5 bg-border" />}
      <span className="absolute left-0 top-1 h-2.5 w-2.5 rounded-full border-2 border-surface bg-accent" />
      <p className="font-mono text-[10.5px] uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-0.5 pb-4 text-sm leading-relaxed text-text">{text}</p>
    </div>
  )
}

function KeyRisk({ text }) {
  return (
    <p className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs leading-relaxed text-warning">
      <span className="font-mono uppercase tracking-wide">Key risk: </span>
      {text}
    </p>
  )
}

function StrategicWedgeCard({ blueprint, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const { opportunityTitle, segment, convictionPercent, vectors, keyRisk } = blueprint
  const title = segment || opportunityTitle
  const status = convictionStatus(convictionPercent)

  return (
    <div className="overflow-hidden rounded-2xl border border-border-strong bg-surface">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start justify-between gap-3 px-5 py-4 text-left"
        aria-expanded={expanded}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <IconLightbulb className="h-4 w-4 shrink-0 text-accent" />
            <h4 className="font-serif text-base font-semibold text-text">{title}</h4>
          </div>
          {!expanded && vectors?.asymmetricWedge && (
            <p className="mt-1.5 text-sm leading-relaxed text-muted-strong">{vectors.asymmetricWedge}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ProvenanceBadge
            status={status}
            label={`${convictionPercent}% conviction`}
            title={`${convictionPercent}% of the four evidence-based links in this chain are backed by a source or profiled competitor data.`}
          />
          <IconChevronDown className={`h-4 w-4 text-muted transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {!expanded && keyRisk && (
        <div className="px-5 pb-4">
          <KeyRisk text={keyRisk} />
        </div>
      )}

      {expanded && (
        <div className="border-t border-border px-5 py-4">
          {_VECTORS.map((vector, i) => (
            <VectorStep key={vector.key} label={vector.label} text={vectors[vector.key]} isLast={i === _VECTORS.length - 1} />
          ))}
          {keyRisk && <KeyRisk text={keyRisk} />}
        </div>
      )}
    </div>
  )
}

export default function StrategicWedgeSection({ blueprints }) {
  const list = blueprints || []
  if (list.length === 0) return null

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-1 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconLightbulb className="h-3.5 w-3.5 text-accent" />
        Strategic Wedge Blueprints
      </h3>
      <p className="mb-3 text-sm text-muted">
        One wedge per customer segment. Open a card for the full Friction → Blindspot → Tailwind → Wedge → Moat chain.
      </p>
      <div className="space-y-3">
        {list.map((blueprint, i) => (
          <StrategicWedgeCard key={i} blueprint={blueprint} defaultExpanded={i === 0} />
        ))}
      </div>
    </div>
  )
}
