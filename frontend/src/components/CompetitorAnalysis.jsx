import { Fragment, useState } from 'react'
import { IconAlertTriangle } from './icons'

// Mirrors backend/agent/competitor_agent.py's _GAP_DISCLOSURE exactly - the
// fallback text it writes when NER found the competitor but couldn't
// generate a real idea-specific differentiation for it. Used here purely
// to tell "auto-identified, generic" competitors apart visually from ones
// with a genuine analyzed gap - never to change what's shown, only how
// confidently it's presented.
const _GAP_DISCLOSURE =
  "Identified automatically from search results - a detailed, idea-specific comparison wasn't generated for this request."

// Matches the backend's actual categories (competitor_agent.py's
// _estimate_price/_estimate_breadth pattern-match these from source text,
// not an LLM call) - a 2x2 version of this grid dropped "mid"/"moderate"
// competitors into "not placed" alongside genuinely unknown ones,
// misrepresenting real data as missing.
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
    <span className="rounded border border-border-strong px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-muted-strong">
      {label}: {value}
    </span>
  )
}

// Confidence isn't a number the backend invents - it's read straight off
// data we already have: a genuinely analyzed gap (not the generic
// disclosure) plus at least one of price/breadth actually classified means
// this competitor has real signal behind it, not just a name NER found.
// Colors it accent (this app's "confirmed/considered" tone) instead of a
// generic gray, so a stronger card visually stands out from an
// auto-identified one rather than looking identical.
function confidenceFor(competitor) {
  const hasGap = competitor.gap && competitor.gap !== _GAP_DISCLOSURE
  const hasClassification = competitor.estimatedPrice !== 'unknown' || competitor.featureBreadth !== 'unknown'
  if (hasGap && hasClassification) return 'high'
  if (hasGap || hasClassification) return 'medium'
  return 'low'
}

const CONFIDENCE_STYLES = {
  high: 'border-accent',
  medium: 'border-border-strong',
  low: 'border-border-strong',
}

// Profiled fields (competitor_agent.py's _profile_with_llm) - "unknown" or
// missing on NER-only competitors, in which case nothing extra renders.
function known(value) {
  return value && value !== 'unknown' ? value : null
}

function TraitList({ title, items, tone }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <p className={`font-mono text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{title}</p>
      <ul className="mt-1 space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-xs leading-snug text-muted-strong">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function formatCount(n) {
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
}

// Logo beside the name. Only an image we know belongs to the competitor
// itself is shown: the App Store icon when the iTunes lookup matched it, or
// the favicon of its own website when we have one. The card's `url` is
// usually the *article* the name was found in, so its favicon would show the
// publisher's logo instead - everything else falls back to the initial.
function CompetitorLogo({ name, enrichment }) {
  const [failed, setFailed] = useState(false)
  let src = null
  if (enrichment?.artworkUrl) {
    src = enrichment.artworkUrl
  } else if (enrichment?.website) {
    const host = hostnameOf(enrichment.website)
    if (host) src = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64`
  }
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        width="32"
        height="32"
        loading="lazy"
        onError={() => setFailed(true)}
        className="h-8 w-8 shrink-0 rounded-lg border border-border object-cover"
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10 font-serif text-sm font-semibold text-accent"
    >
      {name?.trim().charAt(0).toUpperCase() || '?'}
    </span>
  )
}

// One quiet line of real data from the enrichment lookups: rating, review
// count and price for an App Store match; description and founding year for
// a Wikidata match. Shows nothing when the fields aren't there.
function EnrichmentStrip({ enrichment }) {
  if (!enrichment) return null
  const parts = []
  if (enrichment.source === 'itunes') {
    if (typeof enrichment.averageRating === 'number') parts.push(`★ ${enrichment.averageRating.toFixed(1)}`)
    if (enrichment.ratingCount) parts.push(`${formatCount(enrichment.ratingCount)} ratings`)
    if (enrichment.price) parts.push(enrichment.price)
  } else if (enrichment.source === 'wikidata') {
    if (enrichment.description) {
      parts.push(enrichment.description.charAt(0).toUpperCase() + enrichment.description.slice(1))
    }
    if (enrichment.foundedYear) parts.push(`Founded ${enrichment.foundedYear}`)
  }
  if (parts.length === 0) return null
  return <p className="mt-1.5 text-xs font-medium text-muted-strong">{parts.join(' · ')}</p>
}

function CompetitorCard({ competitor }) {
  const { name, offering, url, gap, estimatedPrice, featureBreadth } = competitor
  const enrichment = competitor.enrichment || null
  const classification = known(competitor.classification)
  const pricing = known(competitor.pricing)
  const businessModel = known(competitor.businessModel)
  const strengths = competitor.strengths || []
  const weaknesses = competitor.weaknesses || []
  const confidence = confidenceFor(competitor)
  const isGeneric = !gap || gap === _GAP_DISCLOSURE

  // Use enrichment website as the card link if the source URL is a search snippet
  const cardUrl = enrichment?.website || url

  return (
    <a
      href={cardUrl}
      target="_blank"
      rel="noreferrer"
      className={`block rounded-2xl border-[1.5px] bg-panel p-5 transition-shadow duration-200 hover:shadow-md hover:shadow-black/5 ${CONFIDENCE_STYLES[confidence]}`}
    >
      <div className="flex items-center gap-2.5">
        <CompetitorLogo name={name} enrichment={enrichment} />
        <h4 className="font-serif text-base font-semibold text-text">{name}</h4>
      </div>

      {/* Show PH tagline if it's more informative than the scraped offering */}
      {enrichment?.tagline && (
        <p className="mt-1 text-xs font-medium text-accent/80 leading-snug">{enrichment.tagline}</p>
      )}
      <p className="mt-1.5 text-sm text-muted leading-relaxed">{offering}</p>
      <EnrichmentStrip enrichment={enrichment} />

      <div className="mt-3 flex flex-wrap gap-1.5">
        {classification && (
          <span className="rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-accent">
            {classification}
          </span>
        )}
        <Badge label="Price" value={estimatedPrice} />
        <Badge label="Breadth" value={featureBreadth} />
      </div>

      {(pricing || businessModel) && (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          {pricing && (
            <>
              <dt className="font-mono uppercase tracking-wide text-muted">Pricing</dt>
              <dd className="text-text">{pricing}</dd>
            </>
          )}
          {businessModel && (
            <>
              <dt className="font-mono uppercase tracking-wide text-muted">Model</dt>
              <dd className="text-text">{businessModel}</dd>
            </>
          )}
        </dl>
      )}

      {(strengths.length > 0 || weaknesses.length > 0) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <TraitList title="Strengths" items={strengths} tone="text-success" />
          <TraitList title="Weaknesses" items={weaknesses} tone="text-danger" />
        </div>
      )}

      {gap && (
        <div className="mt-3 flex items-start gap-1.5 border-t border-border pt-3">
          <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
          <p className={`text-sm leading-relaxed ${isGeneric ? 'text-muted' : 'text-text'}`}>{gap}</p>
        </div>
      )}

      {cardUrl && (
        <p className="mt-2 truncate font-mono text-[11px] uppercase tracking-wide text-muted/60">
          {hostnameOf(cardUrl)}
        </p>
      )}
    </a>
  )
}

function UnavailableCard({ error }) {
  return (
    <div className="flex flex-col items-center justify-center p-2 text-center">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">Competitor analysis wasn&apos;t available</p>
      <p className="mt-1 max-w-sm text-xs leading-snug text-muted">
        {error || 'This analysis failed to complete for this request. The rest of your results are still shown below.'}
      </p>
    </div>
  )
}

function PositioningGrid({ competitors }) {
  // Where the founder places their own idea on the grid (click a cell, or drag
  // the chip into one), and which competitor's detail is open. Local, not saved.
  const [mine, setMine] = useState(null)
  const [selected, setSelected] = useState(null)
  const placed = competitors.filter(
    (c) => PRICE_ROWS.includes(c.estimatedPrice) && BREADTH_COLS.includes(c.featureBreadth)
  )
  const unclassified = competitors.filter((c) => !placed.includes(c))

  if (placed.length === 0) return null

  const here = mine ? placed.filter((c) => c.estimatedPrice === mine.row && c.featureBreadth === mine.col) : []
  const open = selected ? placed.find((c) => c.name === selected) : null
  const drop = (row, col) => setMine({ row, col })

  return (
    <div className="mt-5">
      <h3 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted">
        Positioning snapshot
      </h3>
      <p className="mb-3 text-[11px] leading-snug text-muted">
        Approximate placement by price and feature breadth, pattern-matched from
        source text &mdash; not verified market data. Click a competitor for detail,
        and place your own idea to see how crowded that spot is.
      </p>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          draggable
          onDragStart={(e) => e.dataTransfer.setData('text/plain', 'my-idea')}
          className="cursor-grab rounded border border-success/40 bg-success/10 px-2 py-0.5 text-[11px] font-semibold text-success"
          data-testid="my-idea-chip"
        >
          Your idea
        </span>
        <span className="text-[11px] text-muted">Drag it into a cell, or click a cell.</span>
        {mine && (
          <button type="button" onClick={() => setMine(null)} className="font-mono text-[10px] uppercase tracking-wide text-accent">
            Clear
          </button>
        )}
      </div>

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
                  data-testid={`cell-${row}-${col}`}
                  onClick={() => drop(row, col)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    drop(row, col)
                  }}
                  className={`min-h-[3.5rem] cursor-pointer rounded-lg border bg-surface p-1.5 ${
                    mine?.row === row && mine?.col === col ? 'border-success' : 'border-border'
                  }`}
                >
                  <div className="flex flex-wrap gap-1">
                    {cellCompetitors.map((c, i) => (
                      <button
                        type="button"
                        key={i}
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelected(selected === c.name ? null : c.name)
                        }}
                        className={`rounded border px-1.5 py-0.5 text-[10px] leading-snug text-accent ${
                          selected === c.name ? 'border-accent bg-accent/25' : 'border-accent/30 bg-accent/10'
                        }`}
                        title={c.name}
                      >
                        {c.name}
                      </button>
                    ))}
                    {mine?.row === row && mine?.col === col && (
                      <span className="rounded border border-success/40 bg-success/10 px-1.5 py-0.5 text-[10px] font-semibold text-success">
                        Your idea
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>

      {mine && (
        <p className="mt-3 text-xs leading-relaxed text-text" data-testid="grid-verdict">
          {here.length === 0
            ? 'No competitor is placed in this spot - it may be open space, or may mean nobody has made it work.'
            : `${here.length} competitor${here.length === 1 ? '' : 's'} already sit${here.length === 1 ? 's' : ''} here: ${here.map((c) => c.name).join(', ')}. You would need a clear reason to win against ${here.length === 1 ? 'it' : 'them'}.`}
        </p>
      )}

      {open && (
        <div className="mt-3 rounded-xl border border-border bg-surface p-4" data-testid="grid-detail">
          <p className="text-sm font-semibold text-text">{open.name}</p>
          {open.offering && <p className="mt-1 text-sm leading-relaxed text-muted">{open.offering}</p>}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge label="Price" value={open.estimatedPrice} />
            <Badge label="Breadth" value={open.featureBreadth} />
          </div>
          {open.gap && open.gap !== _GAP_DISCLOSURE && (
            <p className="mt-2 text-sm leading-relaxed text-text">{open.gap}</p>
          )}
          {open.url && (
            <a href={open.url} target="_blank" rel="noreferrer" className="mt-2 inline-block font-mono text-[10px] uppercase tracking-wide text-accent">
              {hostnameOf(open.url) || 'Visit'}
            </a>
          )}
        </div>
      )}

      {unclassified.length > 0 && (
        <p className="mt-2 text-[11px] leading-snug text-muted">
          Not placed (price/breadth unknown): {unclassified.map((c) => c.name).join(', ')}
        </p>
      )}
    </div>
  )
}

// Idea-vs-competitor matrix from the profiling pass. Scrolls sideways on
// narrow screens rather than squeezing cells, since columns grow with the
// number of competitors.
function ComparisonMatrix({ rows, competitors }) {
  if (!rows || rows.length === 0) return null
  const names = competitors.map((c) => c.name).filter((n) => rows.some((r) => r.competitors && n in r.competitors))
  if (names.length === 0) return null
  return (
    <div id="sec-compare" className="mt-6 scroll-mt-16">
      <h3 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted">How your idea compares</h3>
      <p className="mb-3 text-[11px] leading-snug text-muted">
        Built only from what the search results say about each competitor &mdash; &ldquo;unknown&rdquo; means the
        sources were silent, not that the feature is missing.
      </p>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[32rem] border-collapse text-left text-xs">
          <thead>
            <tr className="bg-surface">
              <th className="sticky left-0 z-10 bg-surface p-2.5 font-mono text-[10px] uppercase tracking-wide text-muted">Dimension</th>
              <th className="p-2.5 font-mono text-[10px] uppercase tracking-wide text-accent">Your idea</th>
              {names.map((n) => (
                <th key={n} className="p-2.5 font-mono text-[10px] uppercase tracking-wide text-muted">
                  {n}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t border-border align-top">
                <th scope="row" className="sticky left-0 z-10 bg-panel p-2.5 font-semibold text-text">
                  {row.dimension}
                </th>
                <td className="bg-accent/5 p-2.5 text-text">{row.idea}</td>
                {names.map((n) => {
                  const cell = row.competitors?.[n]
                  return (
                    <td key={n} className={`p-2.5 ${known(cell) ? 'text-muted-strong' : 'text-muted/60'}`}>
                      {cell || 'unknown'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SimilarProducts({ products }) {
  if (!Array.isArray(products) || products.length === 0) return null
  return (
    <div className="mt-6">
      <h3 className="mb-1 font-mono text-[11px] uppercase tracking-widest text-muted">
        Similar products on Product Hunt
      </h3>
      <p className="mb-2 text-xs text-muted">
        Found by searching Product Hunt for your idea. These are not part of the competitor analysis or the score.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {products.map((p) => (
          <a
            key={p.name}
            href={p.url || p.website}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-orange-300/60 bg-orange-50/50 p-3 transition-colors hover:bg-orange-50 dark:bg-orange-900/10 dark:hover:bg-orange-900/20"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">{p.name}</span>
              {p.votesCount ? (
                <span className="font-mono text-[10px] text-orange-600 dark:text-orange-400">{p.votesCount}</span>
              ) : null}
            </div>
            {p.tagline && <p className="mt-1 text-xs text-muted">{p.tagline}</p>}
          </a>
        ))}
      </div>
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
      <div>
        <UnavailableCard error="No competitors could be identified from the available sources." />
        <SimilarProducts products={data.similarProducts} />
      </div>
    )
  }

  // Group by how directly each rival competes. Only split into headed groups
  // when at least one competitor actually has a direct/indirect label - if
  // every label is "unknown" a lone "Other mentions" heading would just be noise.
  const groups = [
    { key: 'direct', title: 'Direct rivals', items: competitors.filter((c) => c.classification === 'direct') },
    { key: 'indirect', title: 'Indirect alternatives', items: competitors.filter((c) => c.classification === 'indirect') },
    {
      key: 'other',
      title: 'Other mentions',
      items: competitors.filter((c) => c.classification !== 'direct' && c.classification !== 'indirect'),
    },
  ].filter((g) => g.items.length > 0)
  const hasLabels = competitors.some((c) => c.classification === 'direct' || c.classification === 'indirect')

  return (
    <div>
      {hasLabels ? (
        groups.map((g) => (
          <div key={g.key} className="mb-5">
            <h3 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted">
              {g.title} ({g.items.length})
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {g.items.map((c, i) => (
                <CompetitorCard key={`${g.key}-${i}`} competitor={c} />
              ))}
            </div>
          </div>
        ))
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {competitors.map((c, i) => (
            <CompetitorCard key={i} competitor={c} />
          ))}
        </div>
      )}

      <ComparisonMatrix rows={data.comparisonMatrix} competitors={competitors} />

      <PositioningGrid competitors={competitors} />

      <SimilarProducts products={data.similarProducts} />
    </div>
  )
}
