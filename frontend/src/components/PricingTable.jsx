// One table of every rival's price and where it came from. A price is shown
// only when the sources gave one: the profiled "pricing" text if present, else
// the rough price tier pattern-matched from the source text (marked as an
// estimate), else "Not found in sources" - never a guess.

const TIER_LABEL = { high: 'High-priced', mid: 'Mid-priced', low: 'Low-priced' }

function known(value) {
  return value && value !== 'unknown' ? value : null
}

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

export function priceFor(competitor) {
  const stated = known(competitor.pricing)
  if (stated) return { text: stated, kind: 'stated' }
  const tier = TIER_LABEL[competitor.estimatedPrice]
  if (tier) return { text: tier, kind: 'estimate' }
  return { text: 'Not found in sources', kind: 'unknown' }
}

export default function PricingTable({ competitors }) {
  const rows = (competitors || []).filter((c) => c && c.name)
  if (rows.length === 0) return null
  return (
    <div className="mt-5" data-testid="pricing-table">
      <h3 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted">Pricing, with sources</h3>
      <p className="mb-3 text-[11px] leading-snug text-muted">
        Prices are taken from the pages we read. Where none was stated the row says so, and a rough tier is marked as an estimate.
      </p>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[520px] text-left text-xs">
          <thead className="bg-panel font-mono text-[10px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2">Competitor</th>
              <th className="px-3 py-2">Price</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => {
              const price = priceFor(c)
              const host = hostnameOf(c.url)
              return (
                <tr key={`${c.name}-${i}`} className="border-t border-border">
                  <td className="px-3 py-2 font-semibold text-text">{c.name}</td>
                  <td className={`px-3 py-2 ${price.kind === 'unknown' ? 'text-muted' : 'text-text'}`}>
                    {price.text}
                    {price.kind === 'estimate' && <span className="ml-1.5 rounded-full border border-border-strong px-1.5 py-0.5 text-[9px] uppercase text-muted">Estimate</span>}
                  </td>
                  <td className="px-3 py-2 text-muted-strong">{known(c.businessModel) || '—'}</td>
                  <td className="px-3 py-2">
                    {c.url && host ? (
                      <a href={c.url} target="_blank" rel="noreferrer" className="text-accent hover:text-accent-hover">
                        {host}
                      </a>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
