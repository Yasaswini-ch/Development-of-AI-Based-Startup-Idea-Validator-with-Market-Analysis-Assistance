import { useState } from 'react'
import useCountUp from '../hooks/useCountUp'
import { IconTrendingUp, IconUsers, IconShield, IconNewspaper, IconGlobe, IconDownload, IconLink } from './icons'
import ConfidenceGauge from './ConfidenceGauge'
import MarketOpportunity from './MarketOpportunity'
import CompetitorAnalysis from './CompetitorAnalysis'
import WhiteSpaceAnalysis from './WhiteSpaceAnalysis'
import SwotAnalysis from './SwotAnalysis'
import MvpRecommendations from './MvpRecommendations'
import GtmStrategy from './GtmStrategy'
import ChatAdvisor from './ChatAdvisor'
import ConfidenceDashboard from './ConfidenceDashboard'
import ContradictionsBanner from './ContradictionsBanner'
import ExperimentsActionPlan from './ExperimentsActionPlan'
import { buildSourceMap } from '../lib/sources'

const INITIAL_VISIBLE = 3
const RESEARCH_ANGLES = [
  'Market size & trends',
  'Competitors',
  'Industry news',
  'Customer demand',
  'How others solve this',
]

const ANGLE_ICONS = {
  'market size & trends': IconTrendingUp,
  competitors: IconShield,
  'industry news': IconNewspaper,
  'customer demand': IconUsers,
  'how others solve this': IconTrendingUp,
}

const ANGLE_DESCRIPTIONS = {
  'market size & trends': "How big this market is and which way it's moving.",
  competitors: 'Who else is already solving this, and where they fall short.',
  'industry news': 'Recent shifts among incumbents that change the timing bet.',
  'customer demand': 'What real people say they want, in their own words.',
  'how others solve this': 'The manual workarounds people already build — a signal of what to automate first.',
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

function ResultHeroCard({ r }) {
  return (
    <a
      href={r.url}
      target="_blank"
      rel="noreferrer"
      className="block rounded-2xl border-[1.5px] border-accent bg-panel p-5 transition-shadow duration-200 hover:shadow-md hover:shadow-black/5"
    >
      <div className="flex items-start justify-between gap-3">
        <h4 className="font-serif text-base font-semibold leading-snug text-text">{r.title}</h4>
        {typeof r.score === 'number' && <ScoreBadge score={r.score} />}
      </div>
      {r.snippet && <p className="mt-2 text-sm leading-relaxed text-muted">{r.snippet}</p>}
      <p className="mt-3 truncate border-t border-border pt-2.5 font-mono text-[11px] uppercase tracking-wide text-muted/70">
        {hostnameOf(r.url)}
      </p>
    </a>
  )
}

function ResultRow({ r }) {
  return (
    <a
      href={r.url}
      target="_blank"
      rel="noreferrer"
      className="flex items-start justify-between gap-4 py-3 transition-colors hover:bg-accent/5"
    >
      <div className="min-w-0">
        <p className="text-sm text-text">{r.title}</p>
        {r.snippet && <p className="mt-1 text-xs leading-relaxed text-muted line-clamp-2">{r.snippet}</p>}
        <p className="mt-1 font-mono text-[10px] uppercase tracking-wide text-muted/70">{hostnameOf(r.url)}</p>
      </div>
      {typeof r.score === 'number' && (
        <span className="shrink-0 pt-0.5 font-mono text-[11px] text-muted">
          {Math.round(r.score * 100)}% match
        </span>
      )}
    </a>
  )
}

function AngleGroup({ angle, items }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = iconForAngle(angle)
  const description = ANGLE_DESCRIPTIONS[angle.toLowerCase()]

  const header = (
    <div className="flex items-start gap-3.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
        <Icon className="h-[18px] w-[18px]" />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="flex flex-wrap items-center gap-2 font-serif text-lg font-semibold text-text">
          {angle}
          <span className="rounded-full bg-border px-2 py-0.5 font-mono text-[10px] font-normal text-muted">
            {items.length} source{items.length === 1 ? '' : 's'}
          </span>
        </h3>
        {description && <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">{description}</p>}
      </div>
    </div>
  )

  if (items.length === 0) {
    return (
      <div>
        <div className="mb-4">{header}</div>
        <p className="rounded-xl border border-dashed border-border bg-panel p-4 text-sm text-muted">
          No reliable sources were returned for this research angle.
        </p>
      </div>
    )
  }

  // The single best-matching source per angle gets the full hero-card
  // treatment (not just a hover highlight) so it reads at a glance instead
  // of competing equally with every other card in the group.
  const hasScores = items.some((r) => typeof r.score === 'number')
  const top = hasScores
    ? items.reduce((best, r) => ((r.score ?? -Infinity) > (best.score ?? -Infinity) ? r : best))
    : items[0]
  const rest = items.filter((r) => r !== top)
  const visibleRest = expanded ? rest : rest.slice(0, INITIAL_VISIBLE - 1)

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-3">
        {header}
        {rest.length > INITIAL_VISIBLE - 1 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-1 shrink-0 font-mono text-[11px] uppercase tracking-wide text-accent hover:text-accent-hover"
          >
            {expanded ? 'Show less' : `View all (${items.length})`}
          </button>
        )}
      </div>

      <ResultHeroCard r={top} />

      {visibleRest.length > 0 && (
        <div className="mt-1 flex flex-col divide-y divide-border border-t border-border">
          {visibleRest.map((r, i) => (
            <ResultRow key={r.url || i} r={r} />
          ))}
        </div>
      )}
    </div>
  )
}

const TABS = [
  { key: 'sources', label: 'Sources' },
  { key: 'market', label: 'Market & Competition' },
  { key: 'opportunity', label: 'Opportunity & Risks' },
  { key: 'build', label: 'Build & Launch' },
  { key: 'experiments', label: 'Experiments & Action Plan' },
]

function SectionDivider({ label }) {
  return (
    <h3 className="mb-4 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
      {label}
    </h3>
  )
}

// Copies a ?session=... link (same format the emailed "view this report
// again" link uses, and what CompareIdeas.jsx's inputs accept) to the
// clipboard - the only way to get a session id into Compare without
// having emailed yourself the report first, since there's no account
// system to list past sessions from.
function CopyLinkButton({ sessionId }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    const link = `${window.location.origin}${window.location.pathname}?session=${sessionId}`
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API unavailable (permissions, non-HTTPS context, etc.) -
      // nothing to fall back to here beyond leaving the button inert;
      // the link itself is still valid, just not auto-copied.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex shrink-0 items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
    >
      <IconLink className="h-3.5 w-3.5" />
      {copied ? 'Copied!' : 'Copy comparison link'}
    </button>
  )
}

export default function ValidationResults({
  summary,
  results,
  marketOpportunity,
  competitors,
  whiteSpace,
  swot,
  mvp,
  gtm,
  confidence,
  contradictions,
  experiments,
  actionPlan,
  sessionId,
  apiUrl,
  errors,
}) {
  const [activeTab, setActiveTab] = useState('sources')

  const groups = []
  const order = [...RESEARCH_ANGLES]
  for (const r of results) {
    const key = r.angle || 'Sources'
    if (!order.includes(key)) order.push(key)
  }
  for (const key of order) {
    groups.push({ angle: key, items: results.filter((r) => (r.angle || 'Sources') === key) })
  }

  const competitorCount = competitors?.competitors?.length ?? 0
  const sourceMap = buildSourceMap(results)

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
        {sessionId && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <CopyLinkButton sessionId={sessionId} />
            <a
              href={`${apiUrl}/validate/${sessionId}/pdf`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
            >
              <IconDownload className="h-3.5 w-3.5" />
              Save as PDF
            </a>
          </div>
        )}
      </div>

      <div className="mt-6">
        <ConfidenceDashboard data={confidence} />
      </div>

      <div className="mt-6">
        <ContradictionsBanner data={contradictions} sourceMap={sourceMap} />
      </div>

      {/* Pill tab switcher, not the classic underline-tabs strip - the
          active tab gets its own raised pill instead of a line underneath.
          Sticky so the switcher stays reachable once a tab's content (now
          two merged sections deep) scrolls past a screen's height. */}
      <div className="sticky top-0 z-10 mt-6 max-w-full overflow-x-auto bg-surface/95 py-2 backdrop-blur-sm">
        <div className="inline-flex min-w-max gap-0.5 rounded-full bg-border p-1">
          {TABS.map((t) => {
          const active = activeTab === t.key
          const count = t.key === 'sources' ? results.length : t.key === 'market' ? competitorCount : null
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
      </div>

      <div className="mt-6">
        {activeTab === 'sources' && (
          <div className="space-y-8">
            {groups.length > 0 ? (
              groups.map((g) => <AngleGroup key={g.angle} angle={g.angle} items={g.items} />)
            ) : (
              <p className="rounded-2xl border border-border bg-panel p-6 text-center text-sm text-muted">
                No research sources were returned.
              </p>
            )}
          </div>
        )}

        {activeTab === 'market' && (
          <div className="space-y-8">
            <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Market opportunity" />
              <MarketOpportunity data={marketOpportunity} error={errors?.marketOpportunity} sourceMap={sourceMap} />
            </div>
            <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Competitors" />
              <CompetitorAnalysis data={competitors} error={errors?.competitors} />
            </div>
          </div>
        )}

        {activeTab === 'opportunity' && (
          <div className="space-y-8">
            <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="White space" />
              <WhiteSpaceAnalysis data={whiteSpace} />
            </div>
            <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="SWOT & risks" />
              <SwotAnalysis data={swot} error={errors?.swot} sourceMap={sourceMap} />
            </div>
          </div>
        )}

        {activeTab === 'build' && (
          <div className="space-y-8">
            <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="MVP recommendations" />
              <MvpRecommendations data={mvp} error={errors?.mvp} sourceMap={sourceMap} />
            </div>
            <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Go to market" />
              <GtmStrategy data={gtm} error={errors?.gtm} sourceMap={sourceMap} />
            </div>
          </div>
        )}

        {activeTab === 'experiments' && (
          <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
            <SectionDivider label="Experiments & action plan" />
            <ExperimentsActionPlan
              experiments={experiments}
              actionPlan={actionPlan}
              error={errors?.experiments}
            />
          </div>
        )}
      </div>

      {sessionId && <ChatAdvisor key={sessionId} sessionId={sessionId} apiUrl={apiUrl} />}
    </div>
  )
}
