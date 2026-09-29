import { useState } from 'react'
import { IconMessageCircle } from './icons'
import Citation from './Citation'

// Pillar 1: Direct Voice-of-Market Excerpts (AFFINITY 5-pillar spec §4.1A).
// Renders the verbatim quotes backend/agent/voice_of_market.py extracts
// from real search snippets, in the Customers tab next to the personas they
// describe. The quote is the hero; what kind of signal it is (friction,
// demand, tailwind) is spelled out as a text label rather than only a
// border colour, and each quote carries the same src-N citation marker as
// every other claim in the report.

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

const DIMENSION_STYLE = {
  'Observed Friction': 'text-danger',
  'Demand Signal': 'text-info',
  'Structural Tailwind': 'text-success',
}

function VoiceOfMarketCard({ quote, sourceMap }) {
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

const DIMENSION_ORDER = ['Observed Friction', 'Demand Signal', 'Structural Tailwind']

// Counts span every tagged sentence found in the sources (voiceOfMarketSummary),
// not just the handful of cards shown below, so a thin-looking grid of 2-4
// quotes still communicates how much signal actually backs it up.
function SignalSummary({ summary }) {
  const counts = summary?.dimensionCounts
  if (!counts) return null

  const parts = DIMENSION_ORDER
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

const INITIAL_VISIBLE = 4

// Cards grouped by "theme" (what the quote is about - pricing, onboarding,
// ...) instead of one flat grid, so 8+ quotes on the same topic don't read
// as noise. Preserves the order themes first appear in `quotes` (which is
// already friction-first), except "General" - the catch-all bucket - is
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

// Renders nothing (not even an empty-state) when there are no quotes -
// this section is a bonus on top of the personas, not a required one, so
// an idea with thin community/review coverage just doesn't show it.
export default function VoiceOfMarketSection({ quotes, sourceMap, summary }) {
  const list = quotes || []
  const [filter, setFilter] = useState('All')
  const [expanded, setExpanded] = useState(false)
  if (list.length === 0) return null

  const filterOptions = ['All', ...DIMENSION_ORDER.filter((d) => list.some((q) => q.taggedDimension === d))]
  const filtered = filter === 'All' ? list : list.filter((q) => q.taggedDimension === filter)
  const visible = expanded ? filtered : filtered.slice(0, INITIAL_VISIBLE)
  const hiddenCount = filtered.length - visible.length
  const grouped = groupByTheme(visible)

  function selectFilter(option) {
    setFilter(option)
    setExpanded(false)
  }

  return (
    <div>
      <h3 className="mb-1 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconMessageCircle className="h-3.5 w-3.5 text-accent" />
        Voice of the Market
      </h3>
      <p className="mb-1 text-sm text-muted">What people in the sources actually said, word for word.</p>
      <SignalSummary summary={summary} />
      {filterOptions.length > 2 && <DimensionFilterTabs options={filterOptions} active={filter} onSelect={selectFilter} />}
      {grouped.map(([theme, themeQuotes]) => (
        <div key={theme} className="mb-4 last:mb-0">
          {grouped.length > 1 && (
            <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
              {theme} ({themeQuotes.length})
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {themeQuotes.map((quote, index) => (
              <VoiceOfMarketCard key={quote.sourceId + index} quote={quote} sourceMap={sourceMap} />
            ))}
          </div>
        </div>
      ))}
      {(hiddenCount > 0 || (expanded && filtered.length > INITIAL_VISIBLE)) && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-1 font-mono text-[11px] uppercase tracking-wide text-accent hover:text-accent-hover"
        >
          {hiddenCount > 0 ? `Show ${hiddenCount} more` : 'Show less'}
        </button>
      )}
    </div>
  )
}
