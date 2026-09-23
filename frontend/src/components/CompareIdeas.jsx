import { useEffect, useState } from 'react'
import { IconAlertTriangle, IconX } from './icons'
import { clearCompareList, getCompareList } from '../lib/compareList'

const MAX_SESSIONS = 5
const MIN_SESSIONS = 2

// A pasted "view this report again" email link (see email_delivery.py /
// main.py's _report_url) carries the session id as a ?session= query
// param, not as the id alone - accept either so a user can paste the
// whole link straight from their inbox instead of having to extract the
// id themselves.
function extractSessionId(input) {
  const trimmed = input.trim()
  if (!trimmed) return ''
  try {
    const url = new URL(trimmed)
    return url.searchParams.get('session') || trimmed
  } catch {
    return trimmed
  }
}

function claimText(item) {
  return typeof item === 'string' ? item : item?.text || ''
}

function MetricRow({ label, values, render }) {
  return (
    <tr className="border-t border-border">
      <th className="sticky left-0 bg-panel p-3 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
        {label}
      </th>
      {values.map((value, i) => (
        <td key={i} className="p-3 text-sm text-text align-top">
          {render ? render(value) : value ?? '—'}
        </td>
      ))}
    </tr>
  )
}

// Seeds from the "add to compare" basket (lib/compareList.js, built up from
// HistoryPanel) so arriving here already has real session ids instead of
// two empty inputs - pads up to MIN_SESSIONS with blanks so there's always
// room to add one more by hand.
function seedInputs() {
  const seeded = getCompareList()
  if (seeded.length === 0) return ['', '']
  const padded = [...seeded]
  while (padded.length < MIN_SESSIONS) padded.push('')
  return padded
}

export default function CompareIdeas({ apiUrl, onBack }) {
  const [inputs, setInputs] = useState(seedInputs)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [reports, setReports] = useState(null)
  const [missing, setMissing] = useState([])

  function updateInput(index, value) {
    setInputs((current) => current.map((v, i) => (i === index ? value : v)))
  }

  function addInput() {
    if (inputs.length >= MAX_SESSIONS) return
    setInputs((current) => [...current, ''])
  }

  function removeInput(index) {
    if (inputs.length <= MIN_SESSIONS) return
    setInputs((current) => current.filter((_, i) => i !== index))
  }

  async function runCompare(sessionIds) {
    if (sessionIds.length < MIN_SESSIONS) {
      setError(`Enter at least ${MIN_SESSIONS} session ids or "view report" links to compare.`)
      return
    }

    setIsLoading(true)
    setError('')
    setReports(null)
    setMissing([])

    try {
      const res = await fetch(`${apiUrl}/reports/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionIds }),
      })
      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Could not compare these sessions.')
        setMissing(data.missing || [])
        return
      }

      setReports(data.reports)
      setMissing(data.missing || [])
    } catch {
      setError('Could not reach the server. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  function handleCompare(event) {
    event.preventDefault()
    runCompare(inputs.map(extractSessionId).filter(Boolean))
  }

  // Auto-runs once, only when arriving with a full basket from HistoryPanel
  // ("directly added" per that flow) - then clears the basket so revisiting
  // this screen later doesn't keep re-comparing the same stale set.
  useEffect(() => {
    const seeded = getCompareList()
    if (seeded.length >= MIN_SESSIONS) {
      runCompare(seeded)
      clearCompareList()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-accent">Compare</p>
          <h2 className="font-serif text-2xl text-text">Multi-idea comparison</h2>
        </div>
        <button
          type="button"
          onClick={onBack}
          className="rounded-full border border-border bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
        >
          Back
        </button>
      </div>

      <p className="mb-4 text-sm leading-relaxed text-muted">
        Paste session ids (or full "view report" links from an email) for 2 to {MAX_SESSIONS}{' '}
        past validations to see them side by side, or use "Add to compare" from History to bring
        them here directly.
      </p>

      <form onSubmit={handleCompare} className="rounded-2xl border border-border bg-panel p-5 shadow-sm">
        <div className="space-y-2">
          {inputs.map((value, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                value={value}
                onChange={(e) => updateInput(i, e.target.value)}
                placeholder={`Session id or link #${i + 1}`}
                className="min-w-0 flex-1 rounded-full border border-border bg-surface px-4 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-accent"
              />
              {inputs.length > MIN_SESSIONS && (
                <button
                  type="button"
                  onClick={() => removeInput(i)}
                  aria-label="Remove"
                  className="shrink-0 rounded-full p-1.5 text-muted transition-colors hover:bg-surface hover:text-danger"
                >
                  <IconX className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="mt-3 flex items-center justify-between">
          {inputs.length < MAX_SESSIONS ? (
            <button
              type="button"
              onClick={addInput}
              className="font-mono text-[11px] uppercase tracking-wide text-accent hover:text-accent-hover"
            >
              + Add another
            </button>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={isLoading}
            className="rounded-full bg-accent px-6 py-2.5 font-mono text-xs font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? 'Comparing…' : 'Compare'}
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-danger/20 bg-danger/5 p-3 text-sm text-danger" role="alert">
          <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {missing.length > 0 && (
        <p className="mt-3 text-xs text-muted">
          Not found or expired: {missing.join(', ')}
        </p>
      )}

      {reports && reports.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-border bg-panel shadow-sm">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="sticky left-0 bg-panel p-3 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
                  &nbsp;
                </th>
                {reports.map((r) => (
                  <th key={r.sessionId} className="min-w-[220px] p-3 text-left">
                    <p className="font-serif text-base text-text">{r.ideaSummary?.idea}</p>
                    <p className="mt-1 font-mono text-[10px] uppercase tracking-wide text-muted/70">
                      {r.ideaSummary?.targetCustomer}
                    </p>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <MetricRow
                label="Opportunity score"
                values={reports.map((r) => r.opportunityScore)}
                render={(v) => (typeof v === 'number' && v > 0 ? <span className="font-serif text-xl text-accent">{v}</span> : '—')}
              />
              <MetricRow
                label="Market viability"
                values={reports.map((r) => r.marketViability)}
                render={(v) => (v ? <span className="font-serif text-xl text-accent">{v.score}<span className="text-xs text-muted"> / {v.label}</span></span> : '—')}
              />
              <MetricRow
                label="Confidence"
                values={reports.map((r) => r.confidence?.percentage)}
                render={(v) => (typeof v === 'number' ? `${v}%` : '—')}
              />
              <MetricRow
                label="Market size"
                values={reports.map((r) => r.marketOpportunity?.marketSize)}
                render={(v) => <span className="line-clamp-3 text-xs leading-relaxed">{v || '—'}</span>}
              />
              <MetricRow
                label="Competitors"
                values={reports.map((r) => r.competitors?.competitors)}
                render={(v) => (v?.length ? v.map((c) => c.name).join(', ') : 'None identified')}
              />
              <MetricRow
                label="Top strength"
                values={reports.map((r) => r.swot?.strengths?.[0])}
                render={(v) => <span className="text-xs leading-relaxed">{v ? claimText(v) : '—'}</span>}
              />
              <MetricRow
                label="Top risk"
                values={reports.map((r) => r.swot?.risks?.[0])}
                render={(v) => <span className="text-xs leading-relaxed">{v ? v.risk : '—'}</span>}
              />
              <MetricRow
                label="Top MVP feature"
                values={reports.map((r) => r.mvp?.features?.[0])}
                render={(v) => <span className="text-xs leading-relaxed">{v ? v.feature : '—'}</span>}
              />
              <MetricRow
                label="GTM positioning"
                values={reports.map((r) => r.gtm?.positioning)}
                render={(v) => <span className="text-xs leading-relaxed">{v || '—'}</span>}
              />
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
