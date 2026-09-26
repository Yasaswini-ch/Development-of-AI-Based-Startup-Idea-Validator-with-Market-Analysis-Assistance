import { useState } from 'react'
import { IconChevronDown, IconLightbulb } from './icons'

// Pillar 4: 5-Vector Strategic Wedge Blueprint (AFFINITY 5-pillar spec
// §4.4). Renders whiteSpace.blueprints - computed deterministically by
// backend/agent/strategic_wedge.py - as an expandable Friction -> Blindspot
// -> Tailwind -> Wedge -> Moat chain with a conviction badge, alongside
// (not replacing) the existing opportunity cards above.

const _VECTORS = [
  { key: 'observedFriction', label: 'Observed Friction' },
  { key: 'incumbentBlindspot', label: 'Incumbent Blindspot' },
  { key: 'structuralTailwind', label: 'Structural Tailwind' },
  { key: 'asymmetricWedge', label: 'Asymmetric Wedge' },
  { key: 'defensibilityMoat', label: 'Defensibility Moat' },
]

function convictionClass(percent) {
  if (percent >= 70) return 'border-success/40 bg-success/10 text-success'
  if (percent >= 40) return 'border-accent/30 bg-accent/10 text-accent'
  return 'border-border text-muted-strong'
}

function VectorStep({ label, text, isLast }) {
  return (
    <div className="relative pl-6">
      {!isLast && <div className="absolute left-[5px] top-4 h-full w-0.5 bg-border" />}
      <span className="absolute left-0 top-1 h-2.5 w-2.5 rounded-full border-2 border-surface bg-accent" />
      <p className="font-mono text-[9px] uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-0.5 pb-4 text-sm leading-relaxed text-text">{text}</p>
    </div>
  )
}

function StrategicWedgeCard({ blueprint }) {
  const [expanded, setExpanded] = useState(false)
  const { opportunityTitle, convictionPercent, vectors, keyRisk } = blueprint

  return (
    <div className="rounded-2xl border border-border-strong bg-surface overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          <IconLightbulb className="h-4 w-4 shrink-0 text-accent" />
          <h4 className="font-serif text-base font-semibold text-text">{opportunityTitle}</h4>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide ${convictionClass(convictionPercent)}`}>
            {convictionPercent}% conviction
          </span>
          <IconChevronDown className={`h-4 w-4 text-muted transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border px-5 py-4">
          {_VECTORS.map((vector, i) => (
            <VectorStep key={vector.key} label={vector.label} text={vectors[vector.key]} isLast={i === _VECTORS.length - 1} />
          ))}
          {keyRisk && (
            <p className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-3 text-xs leading-relaxed text-amber-700">
              <span className="font-mono uppercase tracking-wide">Key risk: </span>
              {keyRisk}
            </p>
          )}
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
      <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconLightbulb className="h-3.5 w-3.5 text-accent" />
        Strategic Wedge Blueprints
      </h3>
      <div className="space-y-3">
        {list.map((blueprint, i) => (
          <StrategicWedgeCard key={i} blueprint={blueprint} />
        ))}
      </div>
    </div>
  )
}
