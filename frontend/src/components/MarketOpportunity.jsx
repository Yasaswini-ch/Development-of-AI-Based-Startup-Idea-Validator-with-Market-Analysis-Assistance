import { IconTrendingUp, IconAlertTriangle } from './icons'
import DegradedBanner from './DegradedBanner'
import Citation from './Citation'
import ProvenanceBadge from './ProvenanceBadge'
import MarketViabilityIndex from './MarketViabilityIndex'
import { extractInlineCitations } from '../lib/sources'

// Customer segments and Voice-of-the-Market quotes live in the Customers
// tab (CustomerPersonas.jsx / VoiceOfMarketCard.jsx) - this tab is about
// the market itself: size, trends, and the dynamics breakdown.

// A TAM/SAM/SOM tier is either null (nothing to show - see market_agent.py)
// or a {"text", "sourceIds"} claim, same per-claim shape as trends/segments.
// SAM and SOM may instead be an estimate ({"estimated": true, "assumptions"}),
// shown with an Estimate badge and no citation. Only rendered when at least one
// tier is present, so an idea with no sourced market-sizing breakdown
// doesn't show three empty slots.
function MarketSizeTiers({ tam, sam, som, sourceMap }) {
  const tiers = [
    { label: 'TAM', hint: 'Total addressable market', data: tam },
    { label: 'SAM', hint: 'Serviceable addressable market', data: sam },
    { label: 'SOM', hint: 'Serviceable obtainable market', data: som },
  ].filter((tier) => tier.data?.text)

  if (tiers.length === 0) return null

  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-3">
      {tiers.map((tier) => {
        // An estimate is the model's own working from the TAM, not a figure
        // any source states - drawn differently and always shown with the
        // assumption behind it so it can't be mistaken for a sourced number.
        const estimated = tier.data.estimated === true
        return (
          <div
            key={tier.label}
            className={`rounded-xl bg-surface p-4 ${estimated ? 'border border-dashed border-border-strong' : 'border border-border-strong'}`}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="font-mono text-[10px] uppercase tracking-widest text-accent">{tier.label}</p>
              {estimated && (
                <span className="rounded-full border border-border-strong px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wide text-muted-strong">
                  Estimate
                </span>
              )}
            </div>
            <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-wide text-muted">{tier.hint}</p>
            <p className="mt-2 text-sm leading-relaxed text-text">
              {tier.data.text}
              {!estimated && sourceMap && <Citation sourceIds={tier.data.sourceIds} sourceMap={sourceMap} />}
            </p>
            {estimated && (
              <p className="mt-2 text-xs leading-relaxed text-muted">
                Not from a source. {tier.data.assumptions}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function scoreTier(score) {
  if (score >= 70) return 'Strong opportunity'
  if (score >= 40) return 'Moderate opportunity'
  return 'Early signal'
}

// Deliberately small: the verdict card at the top of the report owns the
// one headline score. This is a secondary, labelled metric.
function OpportunityScore({ score }) {
  return (
    <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
      Opportunity score{' '}
      <span className="text-sm font-semibold normal-case text-text">{score}/100</span>
      <span className="ml-2 normal-case tracking-normal">{scoreTier(score)}</span>
    </p>
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

  const {
    marketSize,
    trends = [],
    segments = [],
    opportunityScore = 0,
    degraded,
    tam,
    sam,
    som,
    viabilityIndex,
  } = data
  if (!marketSize && trends.length === 0 && segments.length === 0) {
    return <UnavailableCard error="No market data could be extracted from the available sources." />
  }
  const inline = extractInlineCitations(marketSize)
  const marketSizeIds = [...new Set([...(data.marketSizeSourceIds || []), ...inline.sourceIds])]

  return (
    <div>
      {degraded && <DegradedBanner />}
      {marketSize && (
        <div>
          <div className="flex items-start gap-2">
            <p className="text-sm text-text leading-relaxed">
              {inline.text}
              {sourceMap && marketSizeIds.length > 0 && <Citation sourceIds={marketSizeIds} sourceMap={sourceMap} />}
            </p>
            <ProvenanceBadge sourceIds={[...marketSizeIds, ...(tam?.sourceIds || []), ...(sam?.sourceIds || []), ...(som?.sourceIds || [])]} />
          </div>
          <MarketSizeTiers tam={tam} sam={sam} som={som} sourceMap={sourceMap} />
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

      <MarketViabilityIndex data={viabilityIndex} sourceMap={sourceMap} />
    </div>
  )
}
