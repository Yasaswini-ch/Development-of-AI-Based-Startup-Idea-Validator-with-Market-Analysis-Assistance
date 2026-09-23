import { useEffect, useMemo, useState } from 'react'
import { getHistory } from '../lib/history'
import { authHeaders } from '../lib/auth'
import ConfidenceGauge from './ConfidenceGauge'
import { IconAlertTriangle, IconGauge } from './icons'

const SEVERITY_ORDER = ['high', 'medium', 'low', 'unknown']
const SEVERITY_STYLES = {
  high: 'bg-danger/15 text-danger',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-accent/10 text-accent',
  unknown: 'bg-border text-muted',
}

function average(values) {
  if (values.length === 0) return null
  return Math.round(values.reduce((sum, v) => sum + v, 0) / values.length)
}

// With a `token` (signed in), the index of "which sessions are mine" comes
// from the server (GET /me/history, scoped to the account). Without one,
// it falls back to the device-local list (lib/history.js) exactly as
// before accounts existed. Either way, this then fetches GET
// /reports/{sessionId} for each entry and rolls the results up into
// aggregate stats.
function useHistoryStats(apiUrl, token) {
  const [entries, setEntries] = useState(token ? [] : getHistory)
  const [reports, setReports] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [missingCount, setMissingCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      let ownEntries = entries
      if (token) {
        try {
          const res = await fetch(`${apiUrl}/me/history`, { headers: authHeaders(token) })
          ownEntries = res.ok ? (await res.json()).entries || [] : []
        } catch {
          ownEntries = []
        }
        if (cancelled) return
        setEntries(ownEntries)
      }

      if (ownEntries.length === 0) {
        if (!cancelled) setIsLoading(false)
        return
      }

      const results = await Promise.allSettled(
        ownEntries.map((entry) =>
          fetch(`${apiUrl}/reports/${entry.sessionId}`, token ? { headers: authHeaders(token) } : undefined).then(
            (res) => (res.ok ? res.json() : null),
          ),
        ),
      )
      if (cancelled) return
      const ok = results.filter((r) => r.status === 'fulfilled' && r.value).map((r) => r.value)
      setReports(ok)
      setMissingCount(ownEntries.length - ok.length)
      setIsLoading(false)
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, token])

  return { entries, reports, isLoading, missingCount }
}

export default function AnalyticsDashboard({ apiUrl, token, onBack }) {
  const { entries, reports, isLoading, missingCount } = useHistoryStats(apiUrl, token)

  const stats = useMemo(() => {
    const opportunityScores = reports
      .map((r) => r.opportunityScore)
      .filter((v) => typeof v === 'number' && v > 0)
    const confidenceScores = reports
      .map((r) => r.confidence?.percentage)
      .filter((v) => typeof v === 'number')

    const severityTally = { high: 0, medium: 0, low: 0, unknown: 0 }
    for (const report of reports) {
      for (const risk of report.swot?.risks ?? []) {
        const key = SEVERITY_STYLES[risk.severity] ? risk.severity : 'unknown'
        severityTally[key] += 1
      }
    }

    const ranked = reports
      .map((r) => ({
        sessionId: r.sessionId,
        idea: r.ideaSummary?.idea || 'Untitled idea',
        score: typeof r.opportunityScore === 'number' ? r.opportunityScore : null,
      }))
      .filter((r) => r.score !== null)
      .sort((a, b) => b.score - a.score)

    return {
      avgOpportunity: average(opportunityScores),
      avgConfidence: average(confidenceScores),
      severityTally,
      totalRisks: Object.values(severityTally).reduce((a, b) => a + b, 0),
      ranked,
    }
  }, [reports])

  return (
    <div className="mx-auto max-w-5xl">
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

      <p className="mb-4 text-sm leading-relaxed text-muted">
        {token
          ? `Rolled up from the ${entries.length} validation${entries.length === 1 ? '' : 's'} saved to your account.`
          : `Rolled up from the ${entries.length} validation${entries.length === 1 ? '' : 's'} saved in your device-local history - sign in to keep this across devices instead of just this browser.`}
      </p>

      {entries.length === 0 && !isLoading ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">
          {token ? 'No validations yet on this account. Run one and its stats will show up here.' : 'No validations yet on this device. Run one and its stats will show up here.'}
        </div>
      ) : isLoading ? (
        <div className="rounded-2xl border border-border bg-panel p-8 text-center font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
          Loading your stats
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">
          None of your saved sessions could be loaded - they may have expired server-side.
        </div>
      ) : (
        <div className="space-y-6">
          {missingCount > 0 && (
            <p className="text-xs text-muted">
              {missingCount} saved session{missingCount === 1 ? '' : 's'} could not be loaded (expired or removed) and
              {missingCount === 1 ? " isn't" : " aren't"} included below.
            </p>
          )}

          <div className="flex flex-wrap items-center gap-8 rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
            <div className="flex items-center gap-4">
              <ConfidenceGauge percent={stats.avgOpportunity ?? 0} size={88} label="OPPORTUNITY" />
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Avg opportunity score</p>
                <p className="mt-1 text-xs text-muted">across {stats.ranked.length} scored idea{stats.ranked.length === 1 ? '' : 's'}</p>
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
                  {SEVERITY_ORDER.map((key) =>
                    stats.severityTally[key] > 0 ? (
                      <div
                        key={key}
                        className={SEVERITY_STYLES[key].split(' ')[0]}
                        style={{ width: `${(stats.severityTally[key] / stats.totalRisks) * 100}%` }}
                        title={`${key}: ${stats.severityTally[key]}`}
                      />
                    ) : null,
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SEVERITY_ORDER.filter((key) => stats.severityTally[key] > 0).map((key) => (
                    <span
                      key={key}
                      className={`rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide ${SEVERITY_STYLES[key]}`}
                    >
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
                    <div
                      key={item.sessionId}
                      className={`flex items-center gap-3 ${
                        i === 0 ? 'rounded-lg border border-accent/30 bg-accent/5 p-2' : ''
                      }`}
                    >
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
    </div>
  )
}
