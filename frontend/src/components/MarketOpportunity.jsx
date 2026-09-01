import { IconLightbulb, IconTrendingUp, IconUsers } from './icons'

function SegmentCard({ segment }) {
  const { segment: name, painPoints, motivations, buyingBehavior } = segment
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h4 className="text-sm font-medium text-text">{name}</h4>
      <dl className="mt-2 space-y-1.5">
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Pain points</dt>
          <dd className="text-sm text-text leading-snug">{painPoints}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Motivations</dt>
          <dd className="text-sm text-text leading-snug">{motivations}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Buying behavior</dt>
          <dd className="text-sm text-text leading-snug">{buyingBehavior}</dd>
        </div>
      </dl>
    </div>
  )
}

export default function MarketOpportunity({ data }) {
  if (!data) return null

  const { marketSize, trends = [], segments = [] } = data
  if (!marketSize && trends.length === 0 && segments.length === 0) return null

  return (
    <div className="mx-auto mt-6 max-w-xl rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
      <div className="flex items-center gap-2">
        <IconLightbulb className="h-4 w-4 text-accent" />
        <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
          Market Opportunity
        </h2>
      </div>

      {marketSize && <p className="mt-3 text-sm text-text leading-relaxed">{marketSize}</p>}

      {trends.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-2 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconTrendingUp className="h-3.5 w-3.5 text-accent" />
            Trends
          </h3>
          <ul className="space-y-1.5">
            {trends.map((t, i) => (
              <li key={i} className="text-sm text-text leading-snug">
                {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {segments.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-2 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconUsers className="h-3.5 w-3.5 text-accent" />
            Customer Segments
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {segments.map((s, i) => (
              <SegmentCard key={i} segment={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
