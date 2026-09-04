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
    percent > 50 ? 'bg-accent/15 text-accent border-accent/30' : 'bg-muted/10 text-muted border-border'
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide ${tier}`}
    >
      {percent}% match
    </span>
  )
}

function ResultCard({ r, isTop }) {
  return (
    <a
      href={r.url}
      target="_blank"
      rel="noreferrer"
      className={`block rounded-xl border bg-panel p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:shadow-lg hover:shadow-black/5 ${
        isTop ? 'border-accent shadow-[0_0_0_1px_var(--color-accent)]' : 'border-border'
      }`}
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
  // The single best-matching source per angle gets a static highlight (not
  // just a hover state), so it reads at a glance instead of every card in
  // the group competing equally for attention.
  const topScore = Math.max(...items.map((r) => (typeof r.score === 'number' ? r.score : -Infinity)))

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
          <ResultCard key={r.url || i} r={r} isTop={r.score === topScore} />
        ))}
      </div>
    </div>
  )
}

const TABS = [
  { key: 'sources', label: 'Sources' },
  { key: 'market', label: 'Market Opportunity' },
  { key: 'competitors', label: 'Competitors' },
]

export default function ValidationResults({ summary, results, marketOpportunity, competitors, errors }) {
  const [activeTab, setActiveTab] = useState('sources')

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

  const competitorCount = competitors?.competitors?.length ?? 0

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-center gap-6 rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
              Validation summary
            </h2>
          </div>
          <p className="mt-3 text-sm text-text leading-relaxed">{summary}</p>
        </div>
        {avgScore !== null && (
          <div className="shrink-0 border-l border-border pl-6 text-right">
            <p className="font-serif text-4xl text-accent">{confidence}%</p>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Confidence</p>
          </div>
        )}
      </div>

      {/* Pill tab switcher, not the classic underline-tabs strip - the
          active tab gets its own raised pill instead of a line underneath. */}
      <div className="mt-6 inline-flex gap-0.5 rounded-full bg-border p-1">
        {TABS.map((t) => {
          const active = activeTab === t.key
          const count = t.key === 'sources' ? results.length : t.key === 'competitors' ? competitorCount : null
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              aria-selected={active}
              className={`flex items-center gap-2 rounded-full px-5 py-2 font-serif text-[15px] transition-colors ${
                active ? 'bg-panel italic text-text shadow-sm' : 'text-muted hover:text-text'
              }`}
            >
              {t.label}
              {count !== null && (
                <span
                  className={`rounded-full px-1.5 py-0.5 font-mono text-[10px] ${
                    active ? 'bg-accent text-white' : 'bg-panel text-muted'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div className="mt-6">
        {activeTab === 'sources' && (
          <div className="space-y-8">
            {groups.map((g) => (
              <AngleGroup key={g.angle} angle={g.angle} items={g.items} />
            ))}
          </div>
        )}

        {activeTab === 'market' && (
          <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
            <MarketOpportunity data={marketOpportunity} error={errors?.marketOpportunity} />
          </div>
        )}

        {activeTab === 'competitors' && (
          <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
            <CompetitorAnalysis data={competitors} error={errors?.competitors} />
          </div>
        )}
      </div>
    </div>
  )
}
