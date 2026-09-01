import { useState } from 'react'
import useCountUp from '../hooks/useCountUp'
import { IconTrendingUp, IconUsers, IconShield, IconNewspaper, IconGlobe } from './icons'
import MarketOpportunity from './MarketOpportunity'
import CompetitorAnalysis from './CompetitorAnalysis'

const INITIAL_VISIBLE = 3

const ANGLE_ICONS = {
  'market size & trends': IconTrendingUp,
  competitors: IconShield,
  'industry news': IconNewspaper,
  'customer demand': IconUsers,
  'how others solve this': IconTrendingUp,
}

function iconForAngle(angle) {
  return ANGLE_ICONS[angle.toLowerCase()] || IconGlobe
}

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

function ScoreBadge({ score }) {
  const percent = useCountUp(Math.round(score * 100), 500)
  const tier =
    percent >= 70
      ? 'bg-accent/15 text-accent border-accent/30'
      : percent >= 50
        ? 'bg-accent/10 text-accent/80 border-accent/20'
        : 'bg-muted/10 text-muted border-border'
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide ${tier}`}
    >
      {percent}% match
    </span>
  )
}

function ResultCard({ r }) {
  return (
    <a
      href={r.url}
      target="_blank"
      rel="noreferrer"
      className="block rounded-xl border border-border bg-panel p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:shadow-lg hover:shadow-black/5"
    >
      <h3 className="mb-1.5 text-sm font-medium leading-snug text-text line-clamp-2">{r.title}</h3>
      <p className="text-sm text-muted leading-relaxed line-clamp-3">{r.snippet}</p>
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-border pt-2">
        <p className="truncate font-mono text-[11px] uppercase tracking-wide text-muted/70">
          {hostnameOf(r.url)}
        </p>
        {typeof r.score === 'number' && <ScoreBadge score={r.score} />}
      </div>
    </a>
  )
}

function AngleGroup({ angle, items }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? items : items.slice(0, INITIAL_VISIBLE)
  const Icon = iconForAngle(angle)

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-muted">
          <Icon className="h-3.5 w-3.5 text-accent" />
          {angle}
        </h3>
        {items.length > INITIAL_VISIBLE && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="font-mono text-[11px] uppercase tracking-wide text-accent hover:text-accent-hover"
          >
            {expanded ? 'Show less' : `View all (${items.length})`}
          </button>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((r, i) => (
          <ResultCard key={r.url || i} r={r} />
        ))}
      </div>
    </div>
  )
}

export default function ValidationResults({ summary, results, marketOpportunity, competitors }) {
  const groups = []
  const order = []
  for (const r of results) {
    const key = r.angle || 'Sources'
    if (!order.includes(key)) order.push(key)
  }
  for (const key of order) {
    groups.push({ angle: key, items: results.filter((r) => (r.angle || 'Sources') === key) })
  }

  const scored = results.filter((r) => typeof r.score === 'number')
  const avgScore = scored.length
    ? scored.reduce((sum, r) => sum + r.score, 0) / scored.length
    : null
  const confidence = useCountUp(avgScore !== null ? Math.round(avgScore * 100) : 0, 800)

  return (
    <div className="mt-6">
      <div className="mx-auto max-w-xl rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
            Validation summary
          </h2>
        </div>
        <div className="mt-3 flex items-start gap-6">
          <p className="flex-1 text-sm text-text leading-relaxed">{summary}</p>
          {avgScore !== null && (
            <div className="shrink-0 border-l border-border pl-6 text-right">
              <p className="font-serif text-4xl text-accent">{confidence}%</p>
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Confidence</p>
            </div>
          )}
        </div>
      </div>

      <MarketOpportunity data={marketOpportunity} />
      <CompetitorAnalysis data={competitors} />

      <div className="mt-8 space-y-8">
        {groups.map((g) => (
          <AngleGroup key={g.angle} angle={g.angle} items={g.items} />
        ))}
      </div>
    </div>
  )
}
