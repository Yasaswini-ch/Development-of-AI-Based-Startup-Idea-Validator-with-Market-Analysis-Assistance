import { IconTrendingUp, IconUsers, IconAlertTriangle } from './icons'
import useCountUp from '../hooks/useCountUp'
import DegradedBanner from './DegradedBanner'
import Citation from './Citation'

// Segment fields (painPoints/motivations/buyingBehavior) are single prose
// strings from the backend, not arrays - splitting on sentence boundaries
// gets a scannable bullet list out of them without needing a backend
// schema change. Falls back to one bullet (the whole string) when there's
// nothing to split on, so short answers still render cleanly.
function toBullets(text) {
  if (!text) return []
  const parts = text
    .split(/(?<=[.;])\s+(?=[A-Z0-9])/)
    .map((s) => s.trim())
    .filter(Boolean)
  return parts.length > 0 ? parts : [text]
}

function BulletField({ label, text }) {
  const bullets = toBullets(text)
  if (bullets.length === 0) return null
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</dt>
      <dd className="mt-1.5">
        <ul className="space-y-1.5">
          {bullets.map((bullet, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-text">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      </dd>
    </div>
  )
}

function SegmentCard({ segment, index, sourceMap }) {
  const { segment: name, painPoints, motivations, buyingBehavior, sourceIds } = segment
  return (
    <div className="rounded-xl border border-border-strong bg-surface p-5">
      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-accent">
        Segment {String(index + 1).padStart(2, '0')}
      </p>
      <h4 className="font-serif text-base font-semibold text-text">
        {name}
        {sourceMap && <Citation sourceIds={sourceIds} sourceMap={sourceMap} />}
      </h4>
      <dl className="mt-3 space-y-3">
        <BulletField label="Pain points" text={painPoints} />
        <BulletField label="Motivations" text={motivations} />
        <BulletField label="Buying behavior" text={buyingBehavior} />
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
    <div className="flex items-baseline gap-3">
      <p className="font-serif text-4xl text-accent">{value}</p>
      <div>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Opportunity Score
        </p>
        <p className={`text-xs font-medium ${tier.className}`}>{tier.label}</p>
      </div>
    </div>
  )
}

function UnavailableCard({ error }) {
  return (
    <div className="flex flex-col items-center justify-center p-2 text-center">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">Market opportunity analysis wasn&apos;t available</p>
      <p className="mt-1 max-w-[16rem] text-xs leading-snug text-muted">
        {error || 'This analysis failed to complete for this request. The rest of your results are still shown below.'}
      </p>
    </div>
  )
}

// No outer card chrome (border/shadow/padding) here - ValidationResults
// wraps this in the tab panel's own card, and the "Market Opportunity" tab
// label already says what section this is, so a repeated heading here
// would just be redundant.
export default function MarketOpportunity({ data, error, sourceMap }) {
  // `data === null` means the backend node failed for this request (per the API
  // contract) - distinct from a normal "nothing to show yet" state, so it gets its
  // own inline message rather than silently rendering nothing.
  if (data === null || data === undefined) {
    return <UnavailableCard error={error} />
  }

  const { marketSize, trends = [], segments = [], opportunityScore = 0, degraded } = data
  if (!marketSize && trends.length === 0 && segments.length === 0) {
    return <UnavailableCard error="No market data could be extracted from the available sources." />
  }

  return (
    <div>
      {degraded && <DegradedBanner />}
      {marketSize && (
        <div>
          <p className="text-sm text-text leading-relaxed">{marketSize}</p>
          {/* A score of 0 means the underlying analysis produced no grounded
              data at all (see backend/agent/opportunity_score.py) - showing
              "0" here would read as a real negative signal, not "unavailable",
              so it's hidden rather than displayed as a plausible-looking number. */}
          {opportunityScore > 0 && (
            <div className="mt-3 border-t border-border pt-3">
              <OpportunityScore score={opportunityScore} />
            </div>
          )}
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
                {/* Each trend is {text, sourceIds} (see docs/unique-features-plan.md
                    §5.1) - typeof-check covers any older/cached plain-string data
                    so this never crashes on a stale cached response either. */}
                {typeof t === 'string' ? t : t.text}
                {typeof t !== 'string' && sourceMap && (
                  <Citation sourceIds={t.sourceIds} sourceMap={sourceMap} />
                )}
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
          {/* Two columns now that this tab has the full page width to
              itself - plenty of room per card, unlike the narrow dashboard
              column this used to sit in. */}
          <div className="grid gap-3 sm:grid-cols-2">
            {segments.map((s, i) => (
              <SegmentCard key={i} segment={s} index={i} sourceMap={sourceMap} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
