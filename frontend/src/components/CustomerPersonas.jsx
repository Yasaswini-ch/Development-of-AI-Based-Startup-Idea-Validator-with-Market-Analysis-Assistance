// Dedicated panel for the customer segments already produced by the market
// agent. MarketOpportunity.jsx also renders SegmentCards inline, but they
// get buried under market-size numbers. This panel surfaces them at the top
// level as the primary customer-persona view, matching the output depth
// founders actually need to validate who they're building for.

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

function PersonaCard({ segment, index }) {
  const { segment: name, painPoints, motivations, buyingBehavior } = segment

  return (
    <div className="rounded-2xl border border-border-strong bg-panel p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 font-mono text-xs font-semibold text-accent">
          {String(index + 1).padStart(2, '0')}
        </span>
        <h4 className="font-serif text-base font-semibold text-text">{name}</h4>
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

export default function CustomerPersonas({ segments }) {
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
          <PersonaCard key={i} segment={seg} index={i} />
        ))}
      </div>
    </div>
  )
}
