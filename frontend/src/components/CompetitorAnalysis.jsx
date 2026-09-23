import { Fragment } from 'react'
import { IconAlertTriangle, IconCheckCircle } from './icons'

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

function CompetitorCard({ competitor }) {
  const { name, offering, url, gap, estimatedPrice, featureBreadth } = competitor
  const confidence = confidenceFor(competitor)
  const isGeneric = !gap || gap === _GAP_DISCLOSURE
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className={`block rounded-2xl border-[1.5px] bg-panel p-5 transition-shadow duration-200 hover:shadow-md hover:shadow-black/5 ${CONFIDENCE_STYLES[confidence]}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-serif text-base font-semibold text-text">{name}</h4>
        {confidence === 'high' ? (
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wide text-accent">
            <IconCheckCircle className="h-3 w-3" />
            Analyzed
          </span>
        ) : (
          <span className="shrink-0 rounded-full border border-border-strong bg-panel px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wide text-muted-strong">
            Auto-identified
          </span>
        )}
      </div>
      <p className="mt-1.5 text-sm text-muted leading-relaxed">{offering}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge label="Price" value={estimatedPrice} />
        <Badge label="Breadth" value={featureBreadth} />
      </div>

      {gap && (
        <div className="mt-3 flex items-start gap-1.5 border-t border-border pt-3">
          <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
          <p className={`text-sm leading-relaxed ${isGeneric ? 'text-muted' : 'text-text'}`}>{gap}</p>
        </div>
      )}

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
        Approximate placement by price and feature breadth, pattern-matched from
        source text &mdash; not verified market data.
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
    <div>
      <div className="grid gap-3 sm:grid-cols-2">
        {competitors.map((c, i) => (
          <CompetitorCard key={i} competitor={c} />
        ))}
      </div>

      <PositioningGrid competitors={competitors} />
    </div>
  )
}
