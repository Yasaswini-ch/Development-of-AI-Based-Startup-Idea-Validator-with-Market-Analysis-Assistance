import { useState } from 'react'
import { IconMessageCircle } from './icons'
import Citation from './Citation'

// Pillar 1: Direct Voice-of-Market Excerpts (AFFINITY 5-pillar spec §4.1A).
// Renders the verbatim quotes backend/agent/voice_of_market.py extracts from
// real search snippets, in the Customers tab. Two independent voices are
// shown: Voice of the Customer (people using/buying a product like this)
// and Voice of the Owner (people running/scaling a business like this) -
// different, equally useful kinds of evidence, so they get separate cards
// and separate dimension vocabularies rather than being merged into one
// generic list. Every quote is the hero; what kind of signal it is is
// spelled out as a text label, and each quote carries the same src-N
// citation marker as every other claim in the report.

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

const CUSTOMER_DIMENSION_ORDER = ['Observed Friction', 'Demand Signal', 'Structural Tailwind']
const OWNER_DIMENSION_ORDER = ['Operational Friction', 'Growth & Traction', 'Strategic Signal']

const DIMENSION_STYLE = {
  'Observed Friction': 'text-danger',
  'Demand Signal': 'text-info',
  'Structural Tailwind': 'text-success',
  'Operational Friction': 'text-danger',
  'Growth & Traction': 'text-success',
  'Strategic Signal': 'text-info',
}

function VoiceCard({ quote, sourceMap }) {
  const host = hostnameOf(quote.url)
  // speakerOrSource is either a community name ("Reddit thread") or just
  // the hostname again - only show it when it adds something.
  const speaker = quote.speakerOrSource && quote.speakerOrSource !== host ? quote.speakerOrSource : null

  return (
    <figure className="flex flex-col rounded-xl border border-border bg-surface p-4">
      {quote.taggedDimension && (
        <p className={`font-mono text-[10.5px] uppercase tracking-widest ${DIMENSION_STYLE[quote.taggedDimension] || 'text-muted'}`}>
          {quote.taggedDimension}
        </p>
      )}
      <blockquote className="mt-1.5 flex-1 font-serif text-[15px] italic leading-relaxed text-text">
        &ldquo;{quote.quote}&rdquo;
        {sourceMap && quote.sourceId && <Citation sourceIds={[quote.sourceId]} sourceMap={sourceMap} />}
      </blockquote>
      <figcaption className="mt-3 flex min-w-0 items-center gap-1.5 text-xs text-muted">
        <span aria-hidden="true">—</span>
        {speaker && (
          <>
            <span className="shrink-0">{speaker}</span>
            {quote.url && <span aria-hidden="true">·</span>}
          </>
        )}
        {quote.url ? (
          <a href={quote.url} target="_blank" rel="noreferrer" className="truncate text-accent hover:text-accent-hover">
            {host || quote.url}
          </a>
        ) : (
          !speaker && <span>{quote.speakerOrSource}</span>
        )}
      </figcaption>
    </figure>
  )
}

// Counts span every tagged sentence found in the sources (the *Summary
// prop), not just the handful of cards shown below, so a thin-looking grid
// of a few quotes still communicates how much signal actually backs it up.
function SignalSummary({ summary, dimensionOrder }) {
  const counts = summary?.dimensionCounts
  if (!counts) return null

  const parts = dimensionOrder
    .filter((dimension) => counts[dimension] > 0)
    .map((dimension) => `${counts[dimension]} ${dimension.toLowerCase()}${counts[dimension] === 1 ? '' : 's'}`)

  if (parts.length === 0) return null

  return (
    <p className="mb-4 text-xs text-muted">
      {parts.join(' · ')}
      {summary.sourcesScanned > 0 && ` found across ${summary.sourcesScanned} sources scanned`}
    </p>
  )
}

// Cards grouped by "theme" (what the quote is about - pricing, onboarding,
// ...) instead of one flat grid, so a long list on the same topic doesn't
// read as noise. Preserves the order themes first appear in `quotes` (which
// is already friction-first), except "General" - the catch-all bucket - is
// always pushed last.
function groupByTheme(quotes) {
  const order = []
  const groups = new Map()
  for (const quote of quotes) {
    const theme = quote.theme || 'General'
    if (!groups.has(theme)) {
      groups.set(theme, [])
      order.push(theme)
    }
    groups.get(theme).push(quote)
  }
  order.sort((a, b) => (a === 'General') - (b === 'General'))
  return order.map((theme) => [theme, groups.get(theme)])
}

function DimensionFilterTabs({ options, active, onSelect }) {
  return (
    <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by signal type">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          role="tab"
          aria-selected={active === option}
          onClick={() => onSelect(option)}
          className={`rounded-full border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wide transition-colors ${
            active === option
              ? 'border-accent bg-accent/10 text-accent'
              : 'border-border text-muted hover:border-border-strong hover:text-text'
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  )
}

// One voice block: every matching quote is shown (nothing hidden behind a
// "show more" toggle) - the filter tabs narrow which quotes are visible,
// they never reduce how much is on the page to start with.
function VoiceBlock({ heading, description, quotes, sourceMap, summary, dimensionOrder }) {
  const list = quotes || []
  const [filter, setFilter] = useState('All')
  if (list.length === 0) return null

  const filterOptions = ['All', ...dimensionOrder.filter((d) => list.some((q) => q.taggedDimension === d))]
  const filtered = filter === 'All' ? list : list.filter((q) => q.taggedDimension === filter)
  const grouped = groupByTheme(filtered)

  return (
    <div>
      <h3 className="mb-1 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconMessageCircle className="h-3.5 w-3.5 text-accent" />
        {heading}
      </h3>
      <p className="mb-1 text-sm text-muted">{description}</p>
      <SignalSummary summary={summary} dimensionOrder={dimensionOrder} />
      {filterOptions.length > 2 && <DimensionFilterTabs options={filterOptions} active={filter} onSelect={setFilter} />}
      {grouped.map(([theme, themeQuotes]) => (
        <div key={theme} className="mb-4 last:mb-0">
          {grouped.length > 1 && (
            <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
              {theme} ({themeQuotes.length})
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {themeQuotes.map((quote, index) => (
              <VoiceCard key={quote.sourceId + index} quote={quote} sourceMap={sourceMap} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function VoiceOfCustomerSection({ quotes, sourceMap, summary }) {
  return (
    <VoiceBlock
      heading="Voice of the Customer"
      description="What people using or buying a product like this actually said, word for word."
      quotes={quotes}
      sourceMap={sourceMap}
      summary={summary}
      dimensionOrder={CUSTOMER_DIMENSION_ORDER}
    />
  )
}

export function VoiceOfOwnerSection({ quotes, sourceMap, summary }) {
  return (
    <VoiceBlock
      heading="Voice of the Owner"
      description="What people running or scaling a business like this actually said, word for word."
      quotes={quotes}
      sourceMap={sourceMap}
      summary={summary}
      dimensionOrder={OWNER_DIMENSION_ORDER}
    />
  )
}

// Renders nothing (not even an empty-state) when there is no data at all -
// this section is a bonus on top of the personas, not a required one, so
// an idea with thin community/review coverage just doesn't show it.
export default function VoiceOfMarketSection({ quotes, sourceMap, summary, ownerQuotes, ownerSummary }) {
  const hasCustomer = (quotes || []).length > 0
  const hasOwner = (ownerQuotes || []).length > 0
  if (!hasCustomer && !hasOwner) return null

  return (
    <div className="space-y-8">
      <VoiceOfCustomerSection quotes={quotes} sourceMap={sourceMap} summary={summary} />
      <VoiceOfOwnerSection quotes={ownerQuotes} sourceMap={sourceMap} summary={ownerSummary} />
    </div>
  )
}
