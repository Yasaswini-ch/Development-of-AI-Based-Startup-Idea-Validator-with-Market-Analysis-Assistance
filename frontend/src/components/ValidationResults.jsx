import { useEffect, useRef, useState } from 'react'
import useCountUp from '../hooks/useCountUp'
import { IconTrendingUp, IconUsers, IconShield, IconNewspaper, IconGlobe, IconDownload, IconLink } from './icons'
import MarketOpportunity from './MarketOpportunity'
import CompetitorAnalysis from './CompetitorAnalysis'
import WhiteSpaceAnalysis from './WhiteSpaceAnalysis'
import SwotAnalysis from './SwotAnalysis'
import MvpRecommendations from './MvpRecommendations'
import GtmStrategy from './GtmStrategy'
import ChatAdvisor from './ChatAdvisor'
import ConfidenceDashboard from './ConfidenceDashboard'
import EvidenceAudit from './EvidenceAudit'
import PipelineReplay from './PipelineReplay'
import ContradictionsBanner from './ContradictionsBanner'
import ExperimentsActionPlan from './ExperimentsActionPlan'
import { buildSourceMap } from '../lib/sources'
import IdeaDossier from './IdeaDossier'
import CustomerPersonas from './CustomerPersonas'
import StatsStrip from './StatsStrip'
import AssumptionTracker from './AssumptionTracker'
import BearCase from './BearCase'
import RevenueModels from './RevenueModels'
import VerdictCard from './VerdictCard'
import VerdictWhatIf from './VerdictWhatIf'
import VoiceOfMarketSection from './VoiceOfMarketCard'
import MvpDeliveryRoadmap from './MvpDeliveryRoadmap'

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

// Always renders, even without a numeric score - a source with no
// relevance signal at all is worth flagging just as much as a weak one,
// not silently hidden while every other card shows its number. Tiered the
// same accent/success/danger way as the confidence dashboard, so "how much
// should I trust this source" reads consistently across the whole app.
function ScoreBadge({ score }) {
  const hasScore = typeof score === 'number'
  const percent = useCountUp(hasScore ? Math.round(score * 100) : 0, 500)
  if (!hasScore) {
    return (
      <span className="shrink-0 rounded-full border border-border-strong bg-panel px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide text-muted-strong">
        Not scored
      </span>
    )
  }
  const tier =
    percent >= 67
      ? 'bg-success/15 text-success border-success/40'
      : percent >= 34
        ? 'bg-accent/15 text-accent border-accent/30'
        : 'bg-danger/10 text-danger border-danger/30'
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
      className={`block rounded-2xl bg-panel p-5 transition-shadow duration-200 hover:shadow-md hover:shadow-black/5 ${
        isTop ? 'border-[1.5px] border-accent' : 'border border-border-strong'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <h4 className="font-serif text-base font-semibold leading-snug text-text">{r.title}</h4>
        <ScoreBadge score={r.score} />
      </div>
      {r.snippet && <p className="mt-2 text-sm leading-relaxed text-muted">{r.snippet}</p>}
      <p className="mt-3 truncate border-t border-border pt-2.5 font-mono text-[11px] uppercase tracking-wide text-muted/70">
        {hostnameOf(r.url)}
      </p>
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

      <div className="space-y-3">
        <ResultCard r={top} isTop />
        {visibleRest.map((r, i) => (
          <ResultCard key={r.url || i} r={r} />
        ))}
      </div>
    </div>
  )
}

const TABS = [
  { key: 'sources', label: 'Evidence' },
  { key: 'market', label: 'Market' },
  { key: 'competitors', label: 'Competitors' },
  { key: 'customers', label: 'Customers' },
  { key: 'gaps', label: 'Gaps' },
  { key: 'risks', label: 'Risks' },
  { key: 'build', label: 'Build & Ship' },
  { key: 'experiments', label: 'Roadmap' },
]

// A tab's count badge: how many items the tab holds, with a tooltip saying
// what is being counted, since each tab counts something different. Neutral
// on the active tab too - a coral badge read like an unread-notification dot.
// Tabs whose content isn't a list of items (Build & Ship, Roadmap) get none.
function tabBadge(key, { results, competitorCount, marketOpportunity, whiteSpace }) {
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
  const counts = {
    sources: [results.length, 'source'],
    competitors: [competitorCount, 'competitor'],
    customers: [marketOpportunity?.segments?.length ?? 0, 'customer segment'],
    gaps: [whiteSpace?.opportunities?.length ?? 0, 'market gap'],
  }
  if (!counts[key]) return null
  const [count, word] = counts[key]
  return { count, title: plural(count, word) }
}

function SectionDivider({ label }) {
  return (
    <h3 className="mb-4 flex items-center gap-2 border-b border-border-strong pb-2.5 font-mono text-[11px] font-semibold uppercase tracking-widest text-text">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
      {label}
    </h3>
  )
}

function SectionNav({ sections }) {
  function scrollTo(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <div className="mb-5 flex flex-wrap gap-2">
      {sections.map((s, i) => (
        <button
          key={s.id}
          onClick={() => scrollTo(s.id)}
          className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[10px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
        >
          <span className="font-bold text-accent">§{String(i + 1).padStart(2, '0')}</span>
          {s.label}
        </button>
      ))}
    </div>
  )
}

function GroundingNotice({ message }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/5 px-4 py-3">
      <span className="mt-0.5 shrink-0 text-warning-bright">⚠</span>
      <p className="text-sm leading-relaxed text-warning">{message}</p>
    </div>
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
  idea,
  targetCustomer,
  problem,
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
  assumptions,
  revenueModels,
  verdict,
  marketViability,
  pipelineTrace,
  sessionId,
  apiUrl,
  errors,
}) {
  const [activeTab, setActiveTab] = useState('sources')
  // A chat answer about e.g. competitors or TAM tells the report which
  // section it corresponds to (agent/chat_graph.py's classify_section); this
  // queues a tab switch + scroll so the user sees the answer and the
  // underlying report data together instead of just the chat bubble.
  const [pendingNav, setPendingNav] = useState(null)
  const tabsRef = useRef(null)
  const contentRef = useRef(null)

  // Switching tabs from further down the page used to leave the reader
  // wherever the old scroll offset landed in the new tab's content. When the
  // top of the content is already scrolled above the sticky tab bar, bring it
  // back to just under the bar so the tab is read from its start.
  function selectTab(key) {
    setActiveTab(key)
    requestAnimationFrame(() => {
      const content = contentRef.current
      if (!content) return
      const barHeight = tabsRef.current?.offsetHeight ?? 0
      if (content.getBoundingClientRect().top < barHeight) {
        content.style.scrollMarginTop = `${barHeight}px`
        content.scrollIntoView({ block: 'start' })
      }
    })
  }

  function navigateToSection(section) {
    if (!section?.tab) return
    setActiveTab(section.tab)
    setPendingNav(section)
  }

  useEffect(() => {
    if (!pendingNav || pendingNav.tab !== activeTab) return
    const frame = requestAnimationFrame(() => {
      const target = pendingNav.id ? document.getElementById(pendingNav.id) : null
      const el = target || tabsRef.current
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      if (target) {
        target.classList.add('ring-2', 'ring-accent', 'ring-offset-2', 'ring-offset-surface')
        setTimeout(() => {
          target.classList.remove('ring-2', 'ring-accent', 'ring-offset-2', 'ring-offset-surface')
        }, 2200)
      }
      setPendingNav(null)
    })
    return () => cancelAnimationFrame(frame)
  }, [pendingNav, activeTab])

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

  const segments = marketOpportunity?.segments ?? []

  // Thin-data signals — used to surface grounding notices in context
  const totalConfidenceSources =
    (confidence?.marketGrowth?.total ?? 0) + (confidence?.competitivePressure?.total ?? 0)
  const veryThinData = totalConfidenceSources < 2 && results.length < 4

  return (
    <div className="mt-6 space-y-4">
      {/* Idea dossier — shows back what was submitted so founders can verify interpretation */}
      <IdeaDossier idea={idea} targetCustomer={targetCustomer} problem={problem} />

      {/* The decision first: verdict + the report's one headline score */}
      <VerdictCard data={verdict} />
      <VerdictWhatIf
        verdict={verdict}
        marketViability={marketViability}
        swot={swot}
        assumptions={assumptions}
        confidence={confidence}
        marketOpportunity={marketOpportunity}
      />

      <div className="flex flex-wrap items-center gap-6 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-text">
              Executive summary
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

      {/* KPI strip — counts only; the headline score lives on the verdict */}
      <StatsStrip
        results={results}
        competitors={competitors}
        whiteSpace={whiteSpace}
        marketOpportunity={marketOpportunity}
      />

      <div>
        <ConfidenceDashboard data={confidence} />
      </div>

      <EvidenceAudit marketOpportunity={marketOpportunity} swot={swot} mvp={mvp} gtm={gtm} />
      <PipelineReplay trace={pipelineTrace} />

      {veryThinData && (
        <GroundingNotice message="Fewer than 4 sources were retrieved for this idea — some sections may be inferred rather than grounded in real market data. Try rephrasing the idea or problem statement for a deeper result." />
      )}

      <div>
        <ContradictionsBanner data={contradictions} sourceMap={sourceMap} />
      </div>

      {/* Pill tab switcher */}
      <div ref={tabsRef} className="sticky top-0 z-10 max-w-full overflow-x-auto bg-surface/95 py-2 backdrop-blur-sm">
        <div role="tablist" aria-label="Report sections" className="inline-flex min-w-max gap-0.5 rounded-full bg-border p-1">
          {TABS.map((t) => {
          const active = activeTab === t.key
          const badge = tabBadge(t.key, { results, competitorCount, marketOpportunity, whiteSpace })
          return (
            <button
              key={t.key}
              role="tab"
              onClick={() => selectTab(t.key)}
              aria-selected={active}
              title={badge?.title}
              className={`flex items-center gap-2 rounded-full px-5 py-2 font-serif text-[15px] transition-colors ${
                active
                  ? 'border border-border-strong bg-panel italic text-text shadow-sm'
                  : 'text-muted-strong hover:text-text'
              }`}
            >
              {t.label}
              {badge && (
                <span
                  aria-label={badge.title}
                  className={`rounded-full px-1.5 py-0.5 font-mono text-[10.5px] not-italic ${
                    active ? 'bg-border text-text' : 'bg-panel text-muted'
                  }`}
                >
                  {badge.count}
                </span>
              )}
            </button>
          )
          })}
        </div>
      </div>

      <div ref={contentRef}>
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
            <SectionNav sections={[
              { id: 'sec-market', label: 'Market signal' },
              ...(marketOpportunity?.viabilityIndex?.dimensions?.length > 0 ? [{ id: 'sec-dynamics', label: 'Viability breakdown' }] : []),
            ]} />
            <div id="sec-market" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Market signal" />
              <MarketOpportunity data={marketOpportunity} error={errors?.marketOpportunity} sourceMap={sourceMap} />
            </div>
          </div>
        )}

        {activeTab === 'competitors' && (
          <div className="space-y-8">
            <SectionNav sections={[
              { id: 'sec-competitors', label: 'Competitive field' },
              ...(competitors?.comparisonMatrix?.length > 0 ? [{ id: 'sec-compare', label: 'How you compare' }] : []),
            ]} />
            <div id="sec-competitors" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Competitive field" />
              <CompetitorAnalysis data={competitors} error={errors?.competitors} />
            </div>
          </div>
        )}

        {activeTab === 'customers' && (
          <div className="space-y-4">
            {segments.length === 0 && (
              <GroundingNotice message="No customer demand sources were collected — customer segments couldn't be grounded in real data for this run. Results may reflect general assumptions about your target customer." />
            )}
            <div className="rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              {segments.length > 0 ? (
                <CustomerPersonas segments={segments} sourceMap={sourceMap} />
              ) : (
                <p className="rounded-xl border border-dashed border-border bg-surface p-6 text-center text-sm text-muted">
                  Customer segments were not produced for this run.
                </p>
              )}
            </div>
            {(marketOpportunity?.voiceOfMarket?.length > 0 || marketOpportunity?.voiceOfOwner?.length > 0) && (
              <div className="rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
                <VoiceOfMarketSection
                  quotes={marketOpportunity.voiceOfMarket}
                  summary={marketOpportunity.voiceOfMarketSummary}
                  ownerQuotes={marketOpportunity.voiceOfOwner}
                  ownerSummary={marketOpportunity.voiceOfOwnerSummary}
                  sourceMap={sourceMap}
                />
              </div>
            )}
          </div>
        )}

        {activeTab === 'gaps' && (
          <div className="space-y-8">
            <div id="sec-whitespace" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Whitespace gaps" />
              <WhiteSpaceAnalysis data={whiteSpace} />
            </div>
          </div>
        )}

        {activeTab === 'risks' && (
          <div className="space-y-8">
            <SectionNav sections={[
              { id: 'sec-swot', label: 'Strengths & exposure' },
              { id: 'sec-bearcase', label: 'Bear case' },
              { id: 'sec-assumptions', label: 'Key assumptions' },
            ]} />
            <div id="sec-swot" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Strengths & exposure" />
              <SwotAnalysis data={swot} error={errors?.swot} sourceMap={sourceMap} />
            </div>
            <div id="sec-bearcase" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Bear case — investor objections" />
              <BearCase swot={swot} sourceMap={sourceMap} />
            </div>
            <div id="sec-assumptions" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Key assumptions to validate" />
              <AssumptionTracker data={assumptions} error={errors?.assumptions} sourceMap={sourceMap} />
            </div>
          </div>
        )}

        {activeTab === 'build' && (
          <div className="space-y-8">
            <SectionNav sections={[
              { id: 'sec-mvp', label: 'MVP blueprint' },
              { id: 'sec-revenue', label: 'Revenue models' },
              { id: 'sec-gtm', label: 'Go-to-market' },
            ]} />
            <div id="sec-mvp" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="MVP blueprint" />
              <MvpRecommendations
                data={mvp}
                error={errors?.mvp}
                sourceMap={sourceMap}
                onOpenRoadmap={() => {
                  setActiveTab('experiments')
                  window.scrollTo?.({ top: 0, behavior: 'smooth' })
                }}
              />
            </div>
            <div id="sec-revenue" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Revenue models" />
              <RevenueModels data={revenueModels} error={errors?.revenueModels} sourceMap={sourceMap} />
            </div>
            <div id="sec-gtm" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Go-to-market playbook" />
              <GtmStrategy data={gtm} error={errors?.gtm} sourceMap={sourceMap} roadmap={mvp?.deliveryRoadmap} />
            </div>
          </div>
        )}

        {activeTab === 'experiments' && (
          <div className="space-y-8">
            {mvp?.deliveryRoadmap?.phases?.length > 0 && (
              <SectionNav sections={[
                { id: 'sec-timeline', label: 'Build timeline' },
                { id: 'sec-experiments', label: 'Validation plan' },
              ]} />
            )}
            {mvp?.deliveryRoadmap?.phases?.length > 0 && (
              <div id="sec-timeline" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
                <SectionDivider label="Build timeline" />
                <MvpDeliveryRoadmap data={mvp.deliveryRoadmap} />
              </div>
            )}
            <div id="sec-experiments" className="scroll-mt-16 rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
              <SectionDivider label="Experiments & validation plan" />
              <ExperimentsActionPlan
                experiments={experiments}
                actionPlan={actionPlan}
                error={errors?.experiments}
              />
            </div>
          </div>
        )}
      </div>

      {sessionId && (
        <ChatAdvisor key={sessionId} sessionId={sessionId} apiUrl={apiUrl} onNavigateSection={navigateToSection} />
      )}
    </div>
  )
}
