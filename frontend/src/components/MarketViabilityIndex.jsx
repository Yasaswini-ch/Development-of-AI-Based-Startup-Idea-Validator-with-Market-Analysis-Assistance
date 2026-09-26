import { IconGauge } from './icons'
import Citation from './Citation'
import ProvenanceBadge from './ProvenanceBadge'

// Pillar 2: Market Viability & Dynamics Index (AFFINITY 5-pillar spec
// §4.2) - a 5-axis 1-5 scorecard plus composite, computed by
// backend/agent/viability_score.py's calculate_viability_index() and
// attached to marketOpportunity.viabilityIndex. Deliberately a scorecard
// table, not a radar/SVG chart: five per-axis rationale sentences and
// citations need real reading room, which a compact radar plot doesn't
// leave, and this project has no charting library dependency to draw one
// with (see frontend/package.json).
//
// The composite is shown as a small "x.x / 5 average", not a second big
// 0-100 number: the verdict card owns the report's one headline score, and
// this block is the breakdown of market dynamics behind it.

function tierClass(score) {
  if (score >= 4) return 'text-success'
  if (score === 3) return 'text-accent'
  return 'text-muted-strong'
}

function ScoreDots({ score }) {
  return (
    <div className="flex items-center gap-1" aria-label={`${score} out of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className={`h-2 w-2 rounded-full ${n <= score ? 'bg-accent' : 'bg-border'}`}
        />
      ))}
    </div>
  )
}

function DimensionRow({ dimension, sourceMap }) {
  const { name, score, rating, rationale, sourceIds, provenance } = dimension
  return (
    <div className="grid gap-3 border-b border-border py-4 last:border-b-0 sm:grid-cols-[1fr_auto]">
      <div>
        <div className="flex items-center gap-2">
          <h4 className="font-serif text-sm font-semibold text-text">{name}</h4>
          {sourceMap && sourceIds?.length > 0 && <Citation sourceIds={sourceIds} sourceMap={sourceMap} />}
          <ProvenanceBadge provenance={provenance} sourceIds={sourceIds} />
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-muted">{rationale}</p>
      </div>
      <div className="flex items-center gap-3 sm:flex-col sm:items-end sm:justify-center">
        <ScoreDots score={score} />
        <span className={`font-mono text-[10px] uppercase tracking-wide ${tierClass(score)}`}>{rating}</span>
      </div>
    </div>
  )
}

function AverageScore({ dimensions }) {
  const average = dimensions.reduce((sum, d) => sum + (d.score || 0), 0) / dimensions.length
  return (
    <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
      <span className="text-sm font-semibold normal-case text-text">{average.toFixed(1)} / 5</span> average
    </p>
  )
}

export default function MarketViabilityIndex({ data, sourceMap }) {
  const dimensions = data?.dimensions || []
  if (dimensions.length === 0) return null

  return (
    <div id="sec-dynamics" className="mt-6 scroll-mt-16 border-t border-border pt-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconGauge className="h-3.5 w-3.5 text-accent" />
          Market Viability &amp; Dynamics
        </h3>
        <AverageScore dimensions={dimensions} />
      </div>
      <div className="rounded-xl border border-border-strong bg-surface px-4">
        {dimensions.map((dimension) => (
          <DimensionRow key={dimension.name} dimension={dimension} sourceMap={sourceMap} />
        ))}
      </div>
    </div>
  )
}
