import { IconTrendingUp } from './icons'

// Pillar 5A: GTM Commercial Architecture (AFFINITY 5-pillar spec §4.5A).
// Renders gtm.commercialModel - unit economics + a 3-tier pricing table -
// computed deterministically by backend/agent/commercial_model.py.

function EconomicsStat({ label, value }) {
  return (
    <div className="rounded-xl border border-border-strong bg-surface p-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-1 font-serif text-lg font-semibold text-text">{value}</p>
    </div>
  )
}

function PricingTierCard({ tier, featured }) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        featured ? 'border-accent/50 bg-accent/5' : 'border-border-strong bg-surface'
      }`}
    >
      <p className="font-mono text-[10px] uppercase tracking-widest text-accent">{tier.tierName}</p>
      <p className="mt-1 font-serif text-2xl font-semibold text-text">
        {tier.price}
        <span className="ml-1 font-sans text-xs font-normal text-muted">{tier.billingCycle}</span>
      </p>
      <p className="mt-1 text-xs text-muted">{tier.targetSegment}</p>
      <ul className="mt-3 space-y-1">
        {(tier.includedFeatures || []).map((feature, i) => (
          <li key={i} className="flex gap-2 text-xs leading-relaxed text-text">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
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

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconTrendingUp className="h-3.5 w-3.5 text-accent" />
        Commercial Economics
      </h3>

      {economics && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <EconomicsStat label="Estimated CAC" value={economics.estimatedCac} />
            <EconomicsStat label="Target ARPU" value={economics.targetArpu} />
            <EconomicsStat label="Payback Horizon" value={economics.paybackHorizonMonths} />
            <EconomicsStat label="LTV : CAC" value={economics.ltvToCacRatio} />
          </div>
          <p className="mt-3 text-sm leading-relaxed text-muted">{economics.economicRationale}</p>
        </>
      )}

      {tiers.length > 0 && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {tiers.map((tier, i) => (
            <PricingTierCard key={tier.tierName} tier={tier} featured={i === 1} />
          ))}
        </div>
      )}
    </div>
  )
}
