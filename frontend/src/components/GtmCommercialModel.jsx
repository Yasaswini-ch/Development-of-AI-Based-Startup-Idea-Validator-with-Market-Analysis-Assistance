import { IconTrendingUp } from './icons'
import ProvenanceBadge from './ProvenanceBadge'

// Pillar 5A: GTM Commercial Architecture (AFFINITY 5-pillar spec §4.5A).
// Renders gtm.commercialModel - unit economics + a 3-tier pricing table -
// computed deterministically by backend/agent/commercial_model.py.
//
// Every figure here comes from a few rules of thumb, so the block is badged
// as an estimate and shows the inputs it was built from ("Based on" chips)
// rather than presenting the numbers as measured. No tier is highlighted:
// nothing in the data says which one a founder should lead with.

const PRICE_TIER_LABEL = { low: 'low', mid: 'mid', high: 'high' }

function riskLabel(percent) {
  if (percent >= 67) return 'high'
  if (percent >= 34) return 'medium'
  return 'low'
}

function basisChips(basis) {
  if (!basis) return []
  const chips = []
  const tier = PRICE_TIER_LABEL[basis.priceTier]
  if (tier) {
    chips.push(
      basis.priceTierSource === 'competitors'
        ? `Competitor price level: ${tier}`
        : `Price level from your idea's wording: ${tier}`,
    )
  }
  if (typeof basis.channelCount === 'number') {
    chips.push(
      basis.channelCount > 0
        ? `${basis.channelCount} GTM channel${basis.channelCount === 1 ? '' : 's'} scored`
        : 'No GTM channels scored',
    )
  }
  if (typeof basis.executionRiskPercent === 'number') {
    chips.push(`Execution risk: ${riskLabel(basis.executionRiskPercent)}`)
  }
  return chips
}

function EconomicsStat({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-1 font-sans text-base font-semibold text-text">{value}</p>
    </div>
  )
}

function PricingTierCard({ tier }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-strong">{tier.tierName}</p>
      <p className="mt-1 font-sans text-xl font-semibold text-text">
        {tier.price}
        <span className="ml-1 text-xs font-normal text-muted">{tier.billingCycle}</span>
      </p>
      <p className="mt-1 text-xs text-muted">{tier.targetSegment}</p>
      <ul className="mt-3 space-y-1">
        {(tier.includedFeatures || []).map((feature, i) => (
          <li key={i} className="flex gap-2 text-xs leading-relaxed text-text">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-border-strong" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function GtmCommercialModel({ data }) {
  const economics = data?.unitEconomics
  const tiers = data?.pricingTiers || []
  if (!economics && tiers.length === 0) return null
  const chips = basisChips(data.basis)

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 flex flex-wrap items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconTrendingUp className="h-3.5 w-3.5 text-accent" />
        Commercial Economics
        <ProvenanceBadge
          status="inferred"
          label="Estimate"
          title="Rule-of-thumb estimate from competitor pricing, GTM channel fit and SWOT risk. Use it as a starting point for your own model, not a forecast."
          className="ml-1"
        />
      </h3>

      {chips.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10.5px] uppercase tracking-wide text-muted">Based on</span>
          {chips.map((chip) => (
            <span key={chip} className="rounded-full border border-border bg-panel px-2.5 py-0.5 text-xs text-muted-strong">
              {chip}
            </span>
          ))}
        </div>
      )}

      {economics && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <EconomicsStat label="Estimated CAC" value={economics.estimatedCac} />
            <EconomicsStat label="Target ARPU" value={economics.targetArpu} />
            <EconomicsStat label="Payback" value={economics.paybackHorizonMonths?.replace(/Months?$/, 'months')} />
            <EconomicsStat label="LTV : CAC" value={economics.ltvToCacRatio} />
          </div>
          <p className="mt-3 text-sm leading-relaxed text-muted">{economics.economicRationale}</p>
        </>
      )}

      {tiers.length > 0 && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {tiers.map((tier) => (
            <PricingTierCard key={tier.tierName} tier={tier} />
          ))}
        </div>
      )}
    </div>
  )
}
