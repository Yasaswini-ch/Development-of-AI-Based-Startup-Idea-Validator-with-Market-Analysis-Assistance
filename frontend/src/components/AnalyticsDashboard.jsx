import { useEffect, useMemo, useState } from 'react'
import { getHistory } from '../lib/history'
import { authHeaders } from '../lib/auth'
import ConfidenceGauge from './ConfidenceGauge'
import { IconAlertTriangle, IconGauge } from './icons'
import { DonutChart, HBarChart, LineChart, RadarChart, StackedHBarChart, TagCloud, CHART_COLORS } from './charts'

const SEVERITY_ORDER = ['high', 'medium', 'low', 'unknown']
const SEVERITY_STYLES = {
  high: 'bg-danger/15 text-danger',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-accent/10 text-accent',
  unknown: 'bg-border text-muted',
}
const RISK_COLORS = { high: 'var(--color-danger)', medium: 'var(--color-accent-hover)', low: 'var(--color-success)' }
const RISK_LEGEND = [
  { label: 'High', color: RISK_COLORS.high },
  { label: 'Medium', color: RISK_COLORS.medium },
  { label: 'Low', color: RISK_COLORS.low },
]

function average(values) {
  if (values.length === 0) return null
  return Math.round(values.reduce((sum, v) => sum + v, 0) / values.length)
}

function Kpi({ label, value, sub, tone = 'accent' }) {
  const borderTone = { accent: 'border-t-accent', success: 'border-t-success', warning: 'border-t-accent-hover', danger: 'border-t-danger', info: 'border-t-info' }[tone]
  return (
    <div className={`rounded-xl border border-border border-t-2 ${borderTone} bg-panel p-4`}>
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-2 font-serif text-3xl text-text">{value ?? '—'}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  )
}

function ChartCard({ title, subtitle, children, className = '' }) {
  return (
    <div className={`rounded-2xl border border-border bg-panel p-5 shadow-sm ${className}`}>
      <p className="font-serif text-base text-text">{title}</p>
      {subtitle && <p className="mt-0.5 text-[11px] text-muted">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </div>
  )
}

// --------------------------------------------------
// Signed-in path: GET /me/analytics (server-aggregated, richer)
// --------------------------------------------------

function useUserAnalytics(apiUrl, token) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    setIsLoading(true)
    fetch(`${apiUrl}/me/analytics`, { headers: authHeaders(token) })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('failed'))))
      .then((json) => {
        if (!cancelled) setData(json)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [apiUrl, token])

  return { data, isLoading, error }
}

function scoreColor(score) {
  return score >= 70 ? 'var(--color-success)' : score >= 45 ? 'var(--color-accent-hover)' : 'var(--color-danger)'
}

const USER_SUBTABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'comparison', label: 'Comparison matrix' },
  { id: 'history', label: 'Validation history' },
  { id: 'trends', label: 'Score trends' },
]

function SubNav({ active, onChange }) {
  return (
    <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-border">
      {USER_SUBTABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm transition-colors ${
            active === tab.id ? 'border-accent font-semibold text-accent' : 'border-transparent text-muted hover:text-text'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

function OverviewTab({ data }) {
  const { kpis } = data
  const scoreByIdeaRows = data.scoreByIdea.map((s) => ({ label: s.idea, value: s.score, max: 100, color: scoreColor(s.score) }))
  const assumptionRows = Object.entries(data.assumptionRiskByCategory).map(([category, tally]) => ({
    label: category,
    segments: [
      { label: 'High', value: tally.high, color: RISK_COLORS.high },
      { label: 'Medium', value: tally.medium, color: RISK_COLORS.medium },
      { label: 'Low', value: tally.low, color: RISK_COLORS.low },
    ],
  }))
  const radarAxes = Object.entries(data.viabilityDimensions).map(([key, value]) => ({
    label: { marketDemand: 'Market demand', executionRisk: 'Exec. risk', growthVelocity: 'Growth', competitionClarity: 'Comp. clarity', timing: 'Timing' }[key] || key,
    value,
  }))
  const revenueSlices = data.revenueModelDistribution.map((row, i) => ({ label: row.model, value: row.count, color: CHART_COLORS[i % CHART_COLORS.length] }))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Ideas validated" value={kpis.ideasValidated} tone="accent" />
        <Kpi label="Avg opportunity score" value={kpis.avgOpportunityScore ?? '—'} tone="success" />
        <Kpi label="Best score" value={kpis.bestScore ?? '—'} sub={kpis.bestScoreIdea} tone="info" />
        <Kpi label="High-risk assumptions" value={kpis.highRiskAssumptions} tone="warning" />
        <Kpi label="Complete runs" value={kpis.completeRuns} sub={kpis.degradedRuns > 0 ? `${kpis.degradedRuns} degraded` : undefined} tone="success" />
        <Kpi label="Avg source agreement" value={kpis.avgSourceAgreement !== null ? `${kpis.avgSourceAgreement}%` : '—'} tone="accent" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Opportunity score — all your ideas" subtitle="Higher = stronger market signal" className="lg:col-span-2">
          <HBarChart rows={scoreByIdeaRows} />
        </ChartCard>

        <ChartCard title="Where do your scores fall?" subtitle="Average across five key dimensions (0–100)">
          <div className="h-56">
            <RadarChart axes={radarAxes} />
          </div>
        </ChartCard>

        <ChartCard title="Assumption risk by category" subtitle="High / medium / low uncertainty across your ideas">
          <StackedHBarChart rows={assumptionRows} legend={RISK_LEGEND} />
        </ChartCard>

        <ChartCard title="Suggested revenue models" subtitle="Distribution across your validated ideas">
          <DonutChart slices={revenueSlices} />
        </ChartCard>

        <ChartCard title="Recurring SWOT themes" subtitle="Patterns found across your idea portfolio">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">Strengths</p>
          <TagCloud tags={data.swotThemes.strengths} />
          <p className="mb-2 mt-4 font-mono text-[10px] uppercase tracking-widest text-muted">Risks</p>
          <TagCloud tags={data.swotThemes.risks} tone="risk" />
        </ChartCard>
      </div>
    </div>
  )
}

function CompetitionBadge({ label }) {
  const tone = { Low: 'bg-success/15 text-success', Medium: 'bg-accent/15 text-accent', High: 'bg-danger/15 text-danger', Unclear: 'bg-border text-muted' }[label] || 'bg-border text-muted'
  return <span className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${tone}`}>{label}</span>
}

function ComparisonMatrixTab({ data }) {
  const sortedByScore = [...data.ideas].sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
  const bestSessionId = sortedByScore[0]?.sessionId

  return (
    <div className="space-y-4">
      <p className="rounded-lg border border-info/20 bg-info/10 p-3 text-xs leading-relaxed text-info">
        Every idea side by side across the dimensions that matter most for deciding what to pursue first. Source agreement is what share of the web sources found agree your target market is growing.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-border bg-panel shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface text-left font-mono text-[10px] uppercase tracking-wide text-muted">
              <th className="whitespace-nowrap px-4 py-2.5">Idea</th>
              <th className="px-4 py-2.5">Score</th>
              <th className="px-4 py-2.5">Market size</th>
              <th className="px-4 py-2.5">Competition</th>
              <th className="px-4 py-2.5">Top risk</th>
              <th className="px-4 py-2.5">Revenue model</th>
              <th className="px-4 py-2.5">Source agreement</th>
              <th className="px-4 py-2.5">Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {sortedByScore.map((row) => (
              <tr key={row.sessionId} className={`border-b border-border last:border-0 ${row.sessionId === bestSessionId ? 'bg-success/5' : ''}`}>
                <td className="px-4 py-3">
                  <p className="font-medium text-text">
                    {row.sessionId === bestSessionId && '🏆 '}
                    {row.idea}
                  </p>
                  <p className="font-mono text-[10px] text-muted">{new Date(row.createdAt * 1000).toLocaleDateString()}</p>
                </td>
                <td className="px-4 py-3">
                  <span className="font-serif text-lg" style={{ color: typeof row.score === 'number' ? scoreColor(row.score) : undefined }}>
                    {row.score ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-muted">{row.marketSize || '—'}</td>
                <td className="px-4 py-3">
                  <CompetitionBadge label={row.competitionLabel} />
                </td>
                <td className="px-4 py-3 text-xs text-text">{row.topRisk || '—'}</td>
                <td className="px-4 py-3 text-xs text-muted">{row.revenueModels?.[0]?.name || '—'}</td>
                <td className="px-4 py-3">
                  {typeof row.confidencePercentage === 'number' ? (
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-12 rounded-full bg-border">
                        <div className="h-full rounded-full bg-success" style={{ width: `${row.confidencePercentage}%` }} />
                      </div>
                      <span className="font-mono text-[11px] text-text">{row.confidencePercentage}%</span>
                    </div>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="max-w-[200px] px-4 py-3 text-xs italic text-muted">{row.recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DetailBlock({ title, children }) {
  return (
    <div className="rounded-lg bg-surface p-3.5">
      <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-muted">{title}</p>
      {children}
    </div>
  )
}

function HistoryCard({ idea, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-panel">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-3.5 p-4 text-left hover:bg-surface">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full"
          style={{ background: typeof idea.score === 'number' ? `color-mix(in srgb, ${scoreColor(idea.score)} 15%, transparent)` : 'var(--color-border)' }}
        >
          <span className="font-serif text-lg font-bold" style={{ color: typeof idea.score === 'number' ? scoreColor(idea.score) : 'var(--color-muted)' }}>
            {idea.score ?? '—'}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-text">{idea.idea}</p>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
            {idea.targetCustomer && <span>🎯 {idea.targetCustomer}</span>}
            {idea.problem && <span>❗ {idea.problem}</span>}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-muted">Competition:</span>
            <CompetitionBadge label={idea.competitionLabel} />
            {idea.assumptions.filter((a) => a.uncertainty === 'high').length > 0 && (
              <span className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-[11px] text-muted">
                {idea.assumptions.filter((a) => a.uncertainty === 'high').length} high-risk assumption(s)
              </span>
            )}
            <span className={`rounded-full px-2.5 py-0.5 text-[11px] ${idea.status === 'Complete' ? 'bg-success/15 text-success' : 'bg-accent-hover/15 text-accent-hover'}`}>{idea.status}</span>
          </div>
        </div>
        <span className={`shrink-0 text-muted transition-transform ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && (
        <div className="border-t border-border p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailBlock title="What Affinity found">
              <p className="text-sm text-text">{idea.marketSize || 'No market-size signal available for this run.'}</p>
            </DetailBlock>
            <DetailBlock title="Key risks flagged">
              {idea.risks.length === 0 ? (
                <p className="text-xs text-muted">None flagged.</p>
              ) : (
                <ul className="space-y-1 text-sm text-text">
                  {idea.risks.map((risk, i) => (
                    <li key={i}>
                      <strong className="capitalize">{risk.severity || 'unknown'}:</strong> {risk.risk}
                    </li>
                  ))}
                </ul>
              )}
            </DetailBlock>
            <DetailBlock title="Assumptions to validate">
              {idea.assumptions.length === 0 ? (
                <p className="text-xs text-muted">None flagged.</p>
              ) : (
                <ul className="space-y-1 text-sm text-text">
                  {idea.assumptions.map((a, i) => (
                    <li key={i}>
                      {a.assumption}
                      {a.howToValidate && <span className="text-muted"> — {a.howToValidate}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </DetailBlock>
            <DetailBlock title="Revenue model suggested">
              {idea.revenueModels.length === 0 ? (
                <p className="text-xs text-muted">None suggested.</p>
              ) : (
                <p className="text-sm text-text">
                  {idea.revenueModels[0].name}
                  {idea.revenueModels[0].rationale && <span className="text-muted"> — {idea.revenueModels[0].rationale}</span>}
                </p>
              )}
            </DetailBlock>
          </div>
          {idea.nextSteps.length > 0 && (
            <div className="mt-3 rounded-lg border border-success/20 bg-success/10 p-3.5">
              <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-success">Suggested next steps</p>
              <ul className="list-disc space-y-1 pl-4 text-sm text-text">
                {idea.nextSteps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ValidationHistoryTab({ data }) {
  return (
    <div className="space-y-3">
      {data.ideas.map((idea, i) => (
        <HistoryCard key={idea.sessionId} idea={idea} defaultOpen={i === 0} />
      ))}
    </div>
  )
}

function ScoreTrendsTab({ data }) {
  const avg = data.kpis.avgOpportunityScore
  const scorePoints = data.scoreTrend.map((s) => ({ label: s.idea, y: s.score }))
  const agreementPoints = data.scoreTrend.filter((s) => typeof s.confidencePercentage === 'number').map((s) => ({ label: s.idea, y: s.confidencePercentage }))

  return (
    <div className="space-y-4">
      <ChartCard title="Score over time" subtitle={avg !== null ? `In order of validation date - your average is ${avg}` : 'In order of validation date'}>
        <div className="h-52">
          <LineChart points={scorePoints} yMin={0} yMax={100} />
        </div>
      </ChartCard>
      <ChartCard title="Source agreement trend" subtitle="How consistently web sources back your ideas' market-growth claims, over time">
        <div className="h-44">
          <LineChart points={agreementPoints} yMin={0} yMax={100} color="var(--color-info)" />
        </div>
      </ChartCard>
    </div>
  )
}

function UserAnalyticsView({ apiUrl, token }) {
  const { data, isLoading, error } = useUserAnalytics(apiUrl, token)
  const [tab, setTab] = useState('overview')

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-panel p-8 text-center font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
        Loading your stats
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">
        Couldn't load your analytics right now. Try again in a moment.
      </div>
    )
  }
  if (data.ideasValidated === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">
        No validations yet on this account. Run one and its stats will show up here.
      </div>
    )
  }

  return (
    <div>
      <SubNav active={tab} onChange={setTab} />
      {tab === 'overview' && <OverviewTab data={data} />}
      {tab === 'comparison' && <ComparisonMatrixTab data={data} />}
      {tab === 'history' && <ValidationHistoryTab data={data} />}
      {tab === 'trends' && <ScoreTrendsTab data={data} />}
    </div>
  )
}

// --------------------------------------------------
// Anonymous path (unchanged): device-local history, client-side rollup.
// GET /me/analytics needs a real account to aggregate over, so there's no
// server-side equivalent for this case - see agent/user_analytics.py.
// --------------------------------------------------

function useHistoryStats(apiUrl) {
  const [entries] = useState(getHistory)
  const [reports, setReports] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [missingCount, setMissingCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (entries.length === 0) {
        if (!cancelled) setIsLoading(false)
        return
      }
      const results = await Promise.allSettled(entries.map((entry) => fetch(`${apiUrl}/reports/${entry.sessionId}`).then((res) => (res.ok ? res.json() : null))))
      if (cancelled) return
      const ok = results.filter((r) => r.status === 'fulfilled' && r.value).map((r) => r.value)
      setReports(ok)
      setMissingCount(entries.length - ok.length)
      setIsLoading(false)
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl])

  return { entries, reports, isLoading, missingCount }
}

function AnonymousAnalyticsView({ apiUrl }) {
  const { entries, reports, isLoading, missingCount } = useHistoryStats(apiUrl)

  const stats = useMemo(() => {
    const opportunityScores = reports.map((r) => r.opportunityScore).filter((v) => typeof v === 'number' && v > 0)
    const confidenceScores = reports.map((r) => r.confidence?.percentage).filter((v) => typeof v === 'number')

    const severityTally = { high: 0, medium: 0, low: 0, unknown: 0 }
    for (const report of reports) {
      for (const risk of report.swot?.risks ?? []) {
        const key = SEVERITY_STYLES[risk.severity] ? risk.severity : 'unknown'
        severityTally[key] += 1
      }
    }

    const ranked = reports
      .map((r) => ({ sessionId: r.sessionId, idea: r.ideaSummary?.idea || 'Untitled idea', score: typeof r.opportunityScore === 'number' ? r.opportunityScore : null }))
      .filter((r) => r.score !== null)
      .sort((a, b) => b.score - a.score)

    return { avgOpportunity: average(opportunityScores), avgConfidence: average(confidenceScores), severityTally, totalRisks: Object.values(severityTally).reduce((a, b) => a + b, 0), ranked }
  }, [reports])

  return (
    <>
      <p className="mb-4 text-sm leading-relaxed text-muted">
        Rolled up from the {entries.length} validation{entries.length === 1 ? '' : 's'} saved in your device-local history - sign in to keep this across devices and see the full dashboard.
      </p>

      {entries.length === 0 && !isLoading ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">No validations yet on this device. Run one and its stats will show up here.</div>
      ) : isLoading ? (
        <div className="rounded-2xl border border-border bg-panel p-8 text-center font-mono text-xs uppercase tracking-widest text-muted cursor-blink">Loading your stats</div>
      ) : reports.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">None of your saved sessions could be loaded - they may have expired server-side.</div>
      ) : (
        <div className="space-y-6">
          {missingCount > 0 && (
            <p className="text-xs text-muted">
              {missingCount} saved session{missingCount === 1 ? '' : 's'} could not be loaded (expired or removed) and {missingCount === 1 ? " isn't" : " aren't"} included below.
            </p>
          )}

          <div className="flex flex-wrap items-center gap-8 rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
            <div className="flex items-center gap-4">
              <ConfidenceGauge percent={stats.avgOpportunity ?? 0} size={88} label="OPPORTUNITY" />
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Avg opportunity score</p>
                <p className="mt-1 text-xs text-muted">
                  across {stats.ranked.length} scored idea{stats.ranked.length === 1 ? '' : 's'}
                </p>
              </div>
            </div>
            {stats.avgConfidence !== null && (
              <div className="flex items-center gap-4 border-l border-border pl-8">
                <ConfidenceGauge percent={stats.avgConfidence} size={88} />
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Avg confidence</p>
                  <p className="mt-1 text-xs text-muted">evidence strength, not success odds</p>
                </div>
              </div>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {stats.totalRisks > 0 && (
              <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
                  <IconAlertTriangle className="h-4 w-4 text-accent" />
                  Risks identified, by severity
                </h3>
                <div className="flex h-3 overflow-hidden rounded-full bg-border">
                  {SEVERITY_ORDER.map((key) => (stats.severityTally[key] > 0 ? <div key={key} className={SEVERITY_STYLES[key].split(' ')[0]} style={{ width: `${(stats.severityTally[key] / stats.totalRisks) * 100}%` }} title={`${key}: ${stats.severityTally[key]}`} /> : null))}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SEVERITY_ORDER.filter((key) => stats.severityTally[key] > 0).map((key) => (
                    <span key={key} className={`rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide ${SEVERITY_STYLES[key]}`}>
                      {key}: {stats.severityTally[key]}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {stats.ranked.length > 0 && (
              <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
                  <IconGauge className="h-4 w-4 text-accent" />
                  Ideas ranked by opportunity score
                </h3>
                <div className="space-y-3">
                  {stats.ranked.map((item, i) => (
                    <div key={item.sessionId} className={`flex items-center gap-3 ${i === 0 ? 'rounded-lg border border-accent/30 bg-accent/5 p-2' : ''}`}>
                      <p className="w-1/3 shrink-0 truncate text-sm text-text" title={item.idea}>
                        {i === 0 && <span className="mr-1 text-accent">★</span>}
                        {item.idea}
                      </p>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${item.score}%` }} />
                      </div>
                      <span className="w-10 shrink-0 text-right font-mono text-xs text-muted">{item.score}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

export default function AnalyticsDashboard({ apiUrl, token, onBack }) {
  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-accent">Analytics</p>
          <h2 className="font-serif text-2xl text-text">Your validation stats</h2>
        </div>
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="rounded-full border border-border bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
          >
            Back
          </button>
        )}
      </div>

      {token ? <UserAnalyticsView apiUrl={apiUrl} token={token} /> : <AnonymousAnalyticsView apiUrl={apiUrl} />}
    </div>
  )
}
