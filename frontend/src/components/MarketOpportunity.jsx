import { IconLightbulb, IconTrendingUp, IconUsers, IconAlertTriangle } from './icons'
import useCountUp from '../hooks/useCountUp'

function SegmentCard({ segment }) {
  const { segment: name, painPoints, motivations, buyingBehavior } = segment
  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h4 className="text-sm font-semibold text-text">{name}</h4>
      <dl className="mt-3 space-y-3">
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Pain points</dt>
          <dd className="mt-1 text-sm text-text leading-relaxed">{painPoints}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Motivations</dt>
          <dd className="mt-1 text-sm text-text leading-relaxed">{motivations}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Buying behavior</dt>
          <dd className="mt-1 text-sm text-text leading-relaxed">{buyingBehavior}</dd>
        </div>
      </dl>
    </div>
  )
}

function scoreTier(score) {
  if (score >= 70) {
    return { label: 'Strong opportunity', className: 'text-accent' }
  }
  if (score >= 40) {
    return { label: 'Moderate opportunity', className: 'text-accent/80' }
  }
  return { label: 'Early signal', className: 'text-muted' }
}

function OpportunityScore({ score }) {
  const value = useCountUp(score, 800)
  const tier = scoreTier(score)
  return (
    <div className="shrink-0 border-l border-border pl-6 text-right">
      <p className="font-serif text-4xl text-accent">{value}</p>
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
        Opportunity Score
      </p>
      <p className={`mt-1 text-xs font-medium ${tier.className}`}>{tier.label}</p>
      <p className="mt-0.5 max-w-[9rem] text-[11px] leading-snug text-muted">
        Based on market size, growth trends &amp; competitor density
      </p>
    </div>
  )
}

function UnavailableCard({ error }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-panel/50 p-6 text-center shadow-sm sm:p-8">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">Market opportunity analysis wasn&apos;t available</p>
      <p className="mt-1 max-w-[16rem] text-xs leading-snug text-muted">
        {error || 'This analysis failed to complete for this request. The rest of your results are still shown below.'}
      </p>
    </div>
  )
}

export default function MarketOpportunity({ data, error }) {
  // `data === null` means the backend node failed for this request (per the API
  // contract) - distinct from a normal "nothing to show yet" state, so it gets its
  // own inline message rather than silently rendering nothing.
  if (data === null || data === undefined) {
    return <UnavailableCard error={error} />
  }

  const { marketSize, trends = [], segments = [], opportunityScore = 0 } = data
  if (!marketSize && trends.length === 0 && segments.length === 0) {
    return <UnavailableCard error="No market data could be extracted from the available sources." />
  }

  return (
    <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
      <div className="flex items-center gap-2">
        <IconLightbulb className="h-4 w-4 text-accent" />
        <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
          Market Opportunity
        </h2>
      </div>

      {marketSize && (
        <div className="mt-3 flex items-start gap-6">
          <p className="flex-1 text-sm text-text leading-relaxed">{marketSize}</p>
          {/* A score of 0 means the underlying analysis produced no grounded
              data at all (see backend/agent/opportunity_score.py) - showing
              "0" here would read as a real negative signal, not "unavailable",
              so it's hidden rather than displayed as a plausible-looking number. */}
          {opportunityScore > 0 && <OpportunityScore score={opportunityScore} />}
        </div>
      )}

      {trends.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconTrendingUp className="h-3.5 w-3.5 text-accent" />
            Trends
          </h3>
          <ul className="space-y-2">
            {trends.map((t, i) => (
              <li key={i} className="text-sm text-text leading-relaxed">
                {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {segments.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconUsers className="h-3.5 w-3.5 text-accent" />
            Customer Segments
          </h3>
          {/* Single column, always - these cards hold full sentences per
              field (pain points/motivations/buying behavior), and splitting
              them into sub-columns inside a panel that's already half the
              page width left each card too narrow to read comfortably. */}
          <div className="space-y-3">
            {segments.map((s, i) => (
              <SegmentCard key={i} segment={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
