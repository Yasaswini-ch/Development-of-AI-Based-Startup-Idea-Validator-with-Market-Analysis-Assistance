import Citation from './Citation'
import ProvenanceBadge from './ProvenanceBadge'

// The one place customer segments are shown (the Market & Rivals tab used to
// repeat them as SegmentCards under the market-size numbers). Each persona
// carries its own citation and Grounded/Inferred badge, since this is now
// the only view of the segment claims.

function toBullets(text) {
  if (!text) return []
  const parts = text
    .split(/(?<=[.;])\s+(?=[A-Z0-9])/)
    .map((s) => s.trim())
    .filter(Boolean)
  return parts.length > 0 ? parts : [text]
}

function BulletList({ items }) {
  if (!items || items.length === 0) return null
  return (
    <ul className="mt-1.5 space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm leading-relaxed text-text">
          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

function PersonaCard({ segment, index, sourceMap }) {
  const { segment: name, painPoints, motivations, buyingBehavior, sourceIds } = segment

  return (
    <div className="rounded-2xl border border-border-strong bg-panel p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 font-mono text-xs font-semibold text-accent">
          {String(index + 1).padStart(2, '0')}
        </span>
        <h4 className="font-serif text-base font-semibold text-text">
          {name}
          {sourceMap && sourceIds?.length > 0 && <Citation sourceIds={sourceIds} sourceMap={sourceMap} />}
        </h4>
        <ProvenanceBadge sourceIds={sourceIds} className="ml-auto shrink-0" />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Pain points</p>
          <BulletList items={toBullets(painPoints)} />
        </div>
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Motivations</p>
          <BulletList items={toBullets(motivations)} />
        </div>
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Buying behavior</p>
          <BulletList items={toBullets(buyingBehavior)} />
        </div>
      </div>
    </div>
  )
}

export default function CustomerPersonas({ segments, sourceMap }) {
  if (!segments || segments.length === 0) return null

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-accent">§ Customer segmentation</p>
          <h3 className="mt-1 font-serif text-lg font-semibold text-text">
            Who you're building for
          </h3>
        </div>
        <span className="rounded-full border border-border bg-surface px-3 py-1 font-mono text-[10px] text-muted">
          {segments.length} {segments.length === 1 ? 'segment' : 'segments'}
        </span>
      </div>
      <div className="space-y-4">
        {segments.map((seg, i) => (
          <PersonaCard key={i} segment={seg} index={i} sourceMap={sourceMap} />
        ))}
      </div>
    </div>
  )
}
