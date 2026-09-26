import { IconMessageCircle } from './icons'

// Pillar 1: Direct Voice-of-Market Excerpts (AFFINITY 5-pillar spec §4.1A).
// Renders the verbatim quotes backend/agent/voice_of_market.py extracts
// from real search snippets - prominent quote styling with attribution,
// instead of hiding this text behind Citation.jsx's hover popover only.

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

const _SENTIMENT_STYLE = {
  negative_towards_incumbent: 'border-l-amber-400/60',
  positive_market_signal: 'border-l-success/60',
  neutral: 'border-l-border-strong',
}

function VoiceOfMarketCard({ quote }) {
  const borderClass = _SENTIMENT_STYLE[quote.sentiment] || _SENTIMENT_STYLE.neutral
  const host = hostnameOf(quote.url)

  return (
    <div className={`rounded-xl border border-border bg-surface p-4 border-l-4 ${borderClass}`}>
      <p className="font-serif text-sm italic leading-relaxed text-text">&ldquo;{quote.quote}&rdquo;</p>
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted">
          {quote.speakerOrSource}
        </span>
        {quote.url ? (
          <a
            href={quote.url}
            target="_blank"
            rel="noreferrer"
            className="truncate font-mono text-[10px] uppercase tracking-wide text-accent hover:text-accent-hover"
          >
            {host}
          </a>
        ) : null}
      </div>
    </div>
  )
}

// Renders nothing (not even an empty-state) when there are no quotes -
// this section is a bonus on top of the main market narrative, not a
// required one, so an idea with thin community/review coverage just
// doesn't show it rather than displaying a "no quotes found" message.
export default function VoiceOfMarketSection({ quotes }) {
  const list = quotes || []
  if (list.length === 0) return null

  return (
    <div className="mt-6">
      <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
        <IconMessageCircle className="h-3.5 w-3.5 text-accent" />
        Voice of the Market
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {list.map((quote, index) => (
          <VoiceOfMarketCard key={quote.sourceId + index} quote={quote} />
        ))}
      </div>
    </div>
  )
}
