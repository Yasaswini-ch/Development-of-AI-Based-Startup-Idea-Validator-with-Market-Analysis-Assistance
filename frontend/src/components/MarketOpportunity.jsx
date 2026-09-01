import { IconLightbulb, IconTrendingUp, IconUsers } from './icons'

export default function MarketOpportunity({ data }) {
  if (!data) return null

  const { industrySize, trends = [], targetSegments = [] } = data
  if (!industrySize && trends.length === 0 && targetSegments.length === 0) return null

  return (
    <div className="mx-auto mt-6 max-w-xl rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
      <div className="flex items-center gap-2">
        <IconLightbulb className="h-4 w-4 text-accent" />
        <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
          Market Opportunity
        </h2>
      </div>

      {industrySize && (
        <p className="mt-3 text-sm text-text leading-relaxed">{industrySize}</p>
      )}

      <div className="mt-5 grid gap-6 sm:grid-cols-2">
        {trends.length > 0 && (
          <div>
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

        {targetSegments.length > 0 && (
          <div>
            <h3 className="mb-2 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
              <IconUsers className="h-3.5 w-3.5 text-accent" />
              Target Segments
            </h3>
            <ul className="space-y-1.5">
              {targetSegments.map((s, i) => (
                <li key={i} className="text-sm text-text leading-snug">
                  {s}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
