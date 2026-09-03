import { Fragment } from 'react'
import { IconShield, IconAlertTriangle } from './icons'

const PRICE_ROWS = ['high', 'mid', 'low']
const PRICE_LABELS = { high: 'High price', mid: 'Mid price', low: 'Low price' }
const BREADTH_COLS = ['narrow', 'moderate', 'broad']
const BREADTH_LABELS = { narrow: 'Narrow', moderate: 'Moderate', broad: 'Broad' }

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

function Badge({ label, value }) {
  if (!value || value === 'unknown') return null
  return (
    <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted">
      {label}: {value}
    </span>
  )
}

function CompetitorCard({ competitor }) {
  const { name, offering, url, gap, estimatedPrice, featureBreadth } = competitor
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="block rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent"
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-text">{name}</h4>
      </div>
      <p className="mt-1 text-sm text-muted leading-snug">{offering}</p>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge label="Price" value={estimatedPrice} />
        <Badge label="Breadth" value={featureBreadth} />
      </div>

      <div className="mt-3 flex items-start gap-1.5 border-t border-border pt-2">
        <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <p className="text-sm text-text leading-snug">{gap}</p>
      </div>

      {url && (
        <p className="mt-2 truncate font-mono text-[11px] uppercase tracking-wide text-muted/60">
          {hostnameOf(url)}
        </p>
      )}
    </a>
  )
}

function UnavailableCard({ error }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-panel/50 p-6 text-center shadow-sm sm:p-8">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">Competitor analysis wasn&apos;t available</p>
      <p className="mt-1 max-w-sm text-xs leading-snug text-muted">
        {error || 'This analysis failed to complete for this request. The rest of your results are still shown below.'}
      </p>
    </div>
  )
}

function PositioningGrid({ competitors }) {
  const placed = competitors.filter(
    (c) => PRICE_ROWS.includes(c.estimatedPrice) && BREADTH_COLS.includes(c.featureBreadth)
  )
  const unclassified = competitors.filter((c) => !placed.includes(c))

  if (placed.length === 0) return null

  return (
    <div className="mt-5">
      <h3 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted">
        Positioning snapshot
      </h3>
      <p className="mb-3 text-[11px] leading-snug text-muted">
        Approximate, LLM-estimated placement by price and feature breadth &mdash; not
        verified market data.
      </p>

      <div className="grid grid-cols-[auto_repeat(3,1fr)] gap-1.5">
        <div />
        {BREADTH_COLS.map((col) => (
          <div
            key={col}
            className="text-center font-mono text-[10px] uppercase tracking-wide text-muted"
          >
            {BREADTH_LABELS[col]}
          </div>
        ))}

        {PRICE_ROWS.map((row) => (
          <Fragment key={row}>
            <div className="flex items-center font-mono text-[10px] uppercase tracking-wide text-muted">
              {PRICE_LABELS[row]}
            </div>
            {BREADTH_COLS.map((col) => {
              const cellCompetitors = placed.filter(
                (c) => c.estimatedPrice === row && c.featureBreadth === col
              )
              return (
                <div
                  key={`${row}-${col}`}
                  className="min-h-[3.5rem] rounded-lg border border-border bg-surface p-1.5"
                >
                  <div className="flex flex-wrap gap-1">
                    {cellCompetitors.map((c, i) => (
                      <span
                        key={i}
                        className="rounded border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[10px] leading-snug text-accent"
                        title={c.name}
                      >
                        {c.name}
                      </span>
                    ))}
                  </div>
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>

      {unclassified.length > 0 && (
        <p className="mt-2 text-[11px] leading-snug text-muted">
          Not placed (price/breadth unknown): {unclassified.map((c) => c.name).join(', ')}
        </p>
      )}
    </div>
  )
}

export default function CompetitorAnalysis({ data, error }) {
  // `data === null` means the backend node failed for this request (per the API
  // contract) - distinct from a genuine "no competitors found" result.
  if (data === null || data === undefined) {
    return <UnavailableCard error={error} />
  }

  const { competitors = [] } = data
  if (competitors.length === 0) {
    return (
      <UnavailableCard error="No competitors could be identified from the available sources." />
    )
  }

  return (
    <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
      <div className="flex items-center gap-2">
        <IconShield className="h-4 w-4 text-accent" />
        <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
          Competitor Analysis
        </h2>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {competitors.map((c, i) => (
          <CompetitorCard key={i} competitor={c} />
        ))}
      </div>

      <PositioningGrid competitors={competitors} />
    </div>
  )
}
