import { useEffect, useState } from 'react'
import { authHeaders } from '../lib/auth'
import { DonutChart, HBarChart, LineChart, StackedColumnChart, CHART_COLORS } from './charts'

const TIME_FILTERS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
]

function usePlatformMetrics(apiUrl, token, days) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)
    fetch(`${apiUrl}/admin/platform-metrics?days=${days}`, { headers: authHeaders(token) })
      .then((res) => {
        if (res.status === 403) throw new Error('forbidden')
        if (!res.ok) throw new Error('failed')
        return res.json()
      })
      .then((json) => {
        if (!cancelled) setData(json)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [apiUrl, token, days])

  return { data, isLoading, error }
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

function formatTokens(value) {
  if (value === null || value === undefined) return '—'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
  return String(value)
}

function formatUsd(value) {
  if (value === null || value === undefined) return '—'
  if (value === 0) return '$0'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

const TOKEN_SERIES = [
  { key: 'promptTokens', label: 'Prompt tokens', color: 'var(--color-accent)' },
  { key: 'completionTokens', label: 'Completion tokens', color: 'var(--color-info)' },
]

function TokensAndCost({ usage }) {
  if (!usage) return null
  const columns = usage.daily.map((d) => ({ label: d.date, values: { promptTokens: d.promptTokens, completionTokens: d.completionTokens } }))
  const costPoints = usage.daily.map((d) => ({ label: d.date, y: d.costUsd }))
  const maxModelCost = Math.max(...usage.byModel.map((r) => r.costUsd), 0)
  const modelRows = usage.byModel
    .filter((r) => r.tokens > 0)
    .map((r) => ({ label: r.model, value: r.costUsd, max: maxModelCost || 1, color: 'var(--color-accent)' }))

  return (
    <section className="space-y-4">
      <div>
        <p className="font-serif text-lg text-text">Tokens &amp; cost</p>
        <p className="text-[11px] text-muted">
          Cost is estimated from each call's token counts at list price per model.
          {usage.tokensTrackedCalls < usage.totalCalls && ` ${usage.totalCalls - usage.tokensTrackedCalls} older calls in this window predate token tracking and aren't counted.`}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Tokens used" value={formatTokens(usage.totalTokens)} sub={`${formatTokens(usage.promptTokens)} prompt · ${formatTokens(usage.completionTokens)} completion`} tone="accent" />
        <Kpi label="Estimated cost" value={formatUsd(usage.estimatedCostUsd)} sub="LLM calls, this window" tone="info" />
        <Kpi label="Avg tokens / validation" value={formatTokens(usage.avgTokensPerValidation)} tone="accent" />
        <Kpi label="Avg cost / validation" value={formatUsd(usage.avgCostPerValidationUsd)} tone="info" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Daily token usage" subtitle="Prompt and completion tokens across all LLM calls" className="lg:col-span-2">
          <StackedColumnChart columns={columns} series={TOKEN_SERIES} formatValue={(v) => v.toLocaleString()} />
        </ChartCard>
        <ChartCard title="Daily estimated cost" subtitle="USD per day">
          <div className="h-40">
            <LineChart points={costPoints} yMin={0} color="var(--color-info)" />
          </div>
        </ChartCard>
        <ChartCard title="Estimated cost by model" subtitle="Which models the spend went to">
          <HBarChart rows={modelRows} formatValue={formatUsd} />
        </ChartCard>
      </div>
    </section>
  )
}

function healthColor(rate) {
  if (rate >= 98) return 'var(--color-success)'
  if (rate >= 90) return 'var(--color-info)'
  if (rate >= 80) return 'var(--color-accent-hover)'
  return 'var(--color-danger)'
}

function latencyColor(seconds) {
  if (seconds >= 5) return 'var(--color-danger)'
  if (seconds >= 2) return 'var(--color-accent-hover)'
  return 'var(--color-success)'
}

export default function PlatformHealth({ apiUrl, token, onBack }) {
  const [days, setDays] = useState(30)
  const { data, isLoading, error } = usePlatformMetrics(apiUrl, token, days)

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-accent">Admin</p>
          <h2 className="font-serif text-2xl text-text">Platform health</h2>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1 rounded-lg border border-border bg-panel p-1">
            {TIME_FILTERS.map((f) => (
              <button
                key={f.label}
                type="button"
                onClick={() => setDays(f.days)}
                className={`rounded-md px-2.5 py-1 font-mono text-[11px] ${days === f.days ? 'bg-accent/10 text-accent' : 'text-muted'}`}
              >
                {f.label}
              </button>
            ))}
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
      </div>

      {isLoading ? (
        <div className="rounded-2xl border border-border bg-panel p-8 text-center font-mono text-xs uppercase tracking-widest text-muted cursor-blink">Loading platform metrics</div>
      ) : error === 'forbidden' ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">Admin access required.</div>
      ) : error || !data ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">Couldn't load platform metrics right now.</div>
      ) : (
        <PlatformHealthBody data={data} />
      )}
    </div>
  )
}

function PlatformHealthBody({ data }) {
  const { kpis } = data

  const volumePoints = data.dailyVolume.map((d) => ({ label: d.date, y: d.count }))
  const cachePoints = data.cacheEfficiency.map((d) => ({ label: d.date, y: d.hitRate }))

  const nodeRows = Object.entries(data.nodeSuccessRates)
    .sort((a, b) => a[1] - b[1])
    .map(([node, rate]) => ({ label: node, value: rate, max: 100, color: healthColor(rate) }))

  const latencyRows = Object.entries(data.latencyByNode)
    .sort((a, b) => b[1] - a[1])
    .map(([node, seconds]) => ({ label: node, value: seconds, max: Math.max(...Object.values(data.latencyByNode), 1), color: latencyColor(seconds) }))

  const modelSlices = data.modelUsage.map((row, i) => ({ label: row.model, value: row.count, color: CHART_COLORS[i % CHART_COLORS.length] }))

  const categoryRows = data.topCategories.map((row, i) => ({ label: row.category, value: row.count, color: 'var(--color-accent)' }))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Total validations" value={kpis.totalValidations} tone="accent" />
        <Kpi label="Cache hit rate" value={`${kpis.cacheHitRate}%`} tone="success" />
        <Kpi label="API success rate" value={`${kpis.apiSuccessRate}%`} sub="across LLM-backed nodes" tone="success" />
        <Kpi label="Deep analysis rate" value={`${kpis.deepAnalysisRate}%`} sub="pipeline → email fallback" tone="warning" />
        <Kpi label="Avg pipeline latency" value={kpis.avgLatencySeconds !== null ? `${kpis.avgLatencySeconds}s` : '—'} tone="info" />
        <Kpi label="Active users / week" value={kpis.activeUsersThisWeek} tone="accent" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Daily validation volume" subtitle="Real pipeline invocations per day - cache hits excluded" className="lg:col-span-2">
          <div className="h-40">
            <LineChart points={volumePoints} yMin={0} />
          </div>
        </ChartCard>

        <ChartCard title="Node success rate" subtitle="% of runs where each node completed without error">
          <HBarChart rows={nodeRows} valueSuffix="%" />
        </ChartCard>

        <ChartCard title="Groq / provider model usage" subtitle="Which model served each successful LLM call">
          <DonutChart slices={modelSlices} />
          <p className="mt-4 text-[11px] text-muted">
            Live provider quota remaining isn't shown here - nothing in this codebase polls Groq/Gemini's real rate-limit headers, so that would be invented, not observed.
          </p>
        </ChartCard>

        <ChartCard title="Pipeline latency by node" subtitle="Average wall-clock time per node (seconds)">
          <HBarChart rows={latencyRows} valueSuffix="s" formatValue={(v) => v.toFixed(1)} />
        </ChartCard>

        <ChartCard title="Cache efficiency over time" subtitle="Hit rate % per day">
          <div className="h-40">
            <LineChart points={cachePoints} yMin={0} yMax={100} color="var(--color-success)" />
          </div>
        </ChartCard>

        <ChartCard title="Top idea categories" subtitle="Most frequently validated sectors in this window" className="lg:col-span-2">
          <HBarChart rows={categoryRows} />
        </ChartCard>
      </div>

      <TokensAndCost usage={data.tokenUsage} />

      <div className="rounded-2xl border border-border bg-panel shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <p className="font-serif text-base text-text">Recent pipeline errors</p>
          <span className="rounded-full bg-accent-hover/10 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide text-accent-hover">Live</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface text-left font-mono text-[10px] uppercase tracking-wide text-muted">
                <th className="px-5 py-2.5">Timestamp</th>
                <th className="px-5 py-2.5">Node</th>
                <th className="px-5 py-2.5">Error type</th>
                <th className="px-5 py-2.5">Model chain</th>
                <th className="px-5 py-2.5">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {data.recentErrors.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-6 text-center text-xs text-muted">
                    No errors recorded in this window.
                  </td>
                </tr>
              ) : (
                data.recentErrors.map((row, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-5 py-3 font-mono text-[11px] text-muted">{new Date(row.timestamp).toLocaleString()}</td>
                    <td className="px-5 py-3">
                      <span className="rounded-full bg-accent-hover/10 px-2 py-0.5 font-mono text-[10px] uppercase text-accent-hover">{row.node}</span>
                    </td>
                    <td className="px-5 py-3 text-xs text-text">{row.errorType}</td>
                    <td className="px-5 py-3 font-mono text-[10px] text-muted">{row.modelChain}</td>
                    <td className="px-5 py-3">
                      <span className="rounded-full bg-danger/10 px-2 py-0.5 font-mono text-[10px] uppercase text-danger">{row.outcome}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-border overflow-hidden rounded-2xl border border-border bg-panel">
        <div className="p-4 text-center">
          <p className="font-serif text-2xl text-text">{data.emailDelivery.attempted}</p>
          <p className="mt-1 text-[11px] text-muted">Emails attempted</p>
        </div>
        <div className="p-4 text-center">
          <p className="font-serif text-2xl text-accent">{data.emailDelivery.deliveryRate}%</p>
          <p className="mt-1 text-[11px] text-muted">Delivery rate</p>
        </div>
        <div className="p-4 text-center">
          <p className="font-serif text-2xl text-danger">{data.emailDelivery.failed}</p>
          <p className="mt-1 text-[11px] text-muted">Delivery failures</p>
        </div>
      </div>
    </div>
  )
}
