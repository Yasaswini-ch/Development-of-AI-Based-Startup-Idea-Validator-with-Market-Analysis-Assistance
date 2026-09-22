import { useEffect, useState } from 'react'
import IdeaForm from './components/IdeaForm'
import ValidationResults from './components/ValidationResults'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'
import LandingPage from './components/LandingPage'
import CompareIdeas from './components/CompareIdeas'
import HistoryPanel from './components/HistoryPanel'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import AuthPanel from './components/AuthPanel'
import { IconUser } from './components/icons'
import useCountUp from './hooks/useCountUp'
import useLoadingSteps from './hooks/useLoadingSteps'
import { addHistoryEntry } from './lib/history'
import { authHeaders, clearAuth, getStoredUser, getToken, setAuth } from './lib/auth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const STORAGE_KEY = 'affinity:lastValidation'
const SUBMIT_COOLDOWN_MS = 5000

// Clicking a competitor/result link opens a new tab (target="_blank"), but on
// some browsers - especially mobile - a backgrounded tab can get discarded
// and reloaded from scratch when the user switches back to it. With state
// held only in useState, that reload wiped the results entirely and dropped
// the user back to an empty form, which read as "my results just vanished."
// sessionStorage survives exactly that reload (and clears on an actual tab
// close, so it doesn't linger like localStorage would).
function loadPersisted() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return { ...parsed, updatedAt: parsed.updatedAt ? new Date(parsed.updatedAt) : null }
  } catch {
    return null
  }
}

// GET /reports/{id} returns the canonical report object (report_assembler.py),
// a differently-shaped object than /validate's response - this adapts it
// back to the shape ValidationResults/App already expect. Two known gaps,
// both from the canonical report itself rather than this adapter: it never
// includes whiteSpace (report_assembler.py doesn't carry it), and its
// `sources` are compact_sources()'s trimmed copies (no per-source relevance
// `score`), not the original scored `results` - so a resumed session's
// Sources tab won't show match percentages the way a fresh one does.
function adaptReportToValidation(report) {
  const ideaSummary = report.ideaSummary || {}
  return {
    summary: ideaSummary.summary || '',
    results: report.sources || [],
    marketOpportunity: report.marketOpportunity,
    competitors: report.competitors,
    whiteSpace: null,
    swot: report.swot,
    mvp: report.mvp,
    gtm: report.gtm,
    marketViability: report.marketViability,
    confidence: report.confidence,
    contradictions: report.contradictions,
    experiments: report.experiments,
    actionPlan: report.actionPlan,
    sessionId: report.sessionId,
    errors: report.sectionErrors || {},
  }
}

export default function App() {
  const [persisted] = useState(loadPersisted)
  // Skip the landing page when a session is already mid-flow (a persisted
  // result from before a tab reload, per loadPersisted's own reasoning) -
  // it should only greet a genuinely fresh visitor, not interrupt someone
  // returning to their own results.
  const [view, setView] = useState(persisted?.validation ? 'form' : 'landing')
  const [isLoading, setIsLoading] = useState(false)
  // The button already disables mid-request, but re-enables the instant a
  // response lands - nothing stopped someone from immediately firing another
  // request right after, which is exactly the kind of burst that exhausts
  // the shared Groq quota fastest. A short cooldown after each request
  // finishes (success or failure) spaces that out.
  const [cooldown, setCooldown] = useState(false)
  const [validation, setValidation] = useState(persisted?.validation ?? null)
  const [errorMessage, setErrorMessage] = useState('')
  const [processingMessage, setProcessingMessage] = useState('')
  const [lastSubmission, setLastSubmission] = useState(persisted?.lastSubmission ?? null)
  const [updatedAt, setUpdatedAt] = useState(persisted?.updatedAt ?? null)
  const [authToken, setAuthToken] = useState(getToken)
  const [currentUser, setCurrentUser] = useState(getStoredUser)
  // Remembers where "Sign in" was opened from (landing vs. the main form)
  // purely so its own "Back" button returns there instead of always
  // dropping onto the form - cosmetic, not auth state.
  const [preAuthView, setPreAuthView] = useState('form')
  const loadingStep = useLoadingSteps(isLoading)
  const sourceCount = useCountUp(validation?.results?.length ?? 0)

  // Verifies the token on mount rather than trusting whatever's cached in
  // localStorage - a 30-day-old token could be expired, or a password
  // change could have invalidated it, and showing "signed in as..." for an
  // account the server no longer honors is worse than a beat of extra
  // latency before falling back to signed-out. Only an actual 401 from the
  // server clears the stored credentials - a network-level failure (offline,
  // backend mid-restart) leaves them alone, since that's not evidence the
  // token itself is bad, just that this one check couldn't complete.
  useEffect(() => {
    if (!authToken) return
    let cancelled = false
    fetch(`${API_URL}/auth/me`, { headers: authHeaders(authToken) })
      .then((res) => {
        if (cancelled) return
        if (res.ok) return res.json().then((user) => setCurrentUser(user))
        if (res.status === 401) {
          clearAuth()
          setAuthToken(null)
          setCurrentUser(null)
        }
      })
      .catch(() => {
        // Network-level failure, not a server-confirmed invalid token -
        // nothing to do; the cached credentials stay as they were.
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleAuthenticated({ token, user }) {
    setAuth({ token, user })
    setAuthToken(token)
    setCurrentUser(user)
    setView('form')
  }

  function handleSignOut() {
    clearAuth()
    setAuthToken(null)
    setCurrentUser(null)
  }

  useEffect(() => {
    try {
      if (validation) {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ validation, lastSubmission, updatedAt }))
      } else {
        sessionStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // sessionStorage unavailable (private browsing, storage full, etc.) -
      // the app still works, it just won't survive a tab reload.
    }
  }, [validation, lastSubmission, updatedAt])

  // Resuming from a "view this report again" email link (?session=...) -
  // see email_delivery.py/main.py's _report_url. Runs once on mount only;
  // an already-persisted mid-flow session (loadPersisted, e.g. from a
  // backgrounded-tab reload) takes priority over a stale session id still
  // sitting in the URL bar, so this never clobbers what's already showing.
  useEffect(() => {
    if (persisted?.validation) return
    const sessionId = new URLSearchParams(window.location.search).get('session')
    if (!sessionId) return

    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_URL}/reports/${sessionId}`)
        if (!res.ok || cancelled) return
        const report = await res.json()
        setValidation(adaptReportToValidation(report))
        setUpdatedAt(report.generatedAt ? new Date(report.generatedAt) : new Date())
        setView('form')
        addHistoryEntry({
          sessionId,
          idea: report.ideaSummary?.idea,
          targetCustomer: report.ideaSummary?.targetCustomer,
        })
      } catch {
        // Link expired/invalid, or offline - fall back to the normal empty
        // form silently rather than showing an error for a background
        // convenience feature the user didn't explicitly request this visit.
      } finally {
        // Drop ?session= regardless of outcome so a later manual reload
        // doesn't keep re-fetching (or re-failing) the same stale link.
        window.history.replaceState({}, '', window.location.pathname)
      }
    })()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function validateIdea(payload) {
    setIsLoading(true)
    setErrorMessage('')
    setValidation(null)
    setLastSubmission(payload)
    setProcessingMessage('')

    try {
      const res = await fetch(`${API_URL}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders(authToken) },
        body: JSON.stringify(payload),
      })
      const data = await res.json()

      if (res.status === 202 && data.status === 'processing') {
        // Taking longer than the server's threshold - it keeps working in
        // the background and will email the report; poll the job here too
        // so the tab updates live if the user stays on the page.
        setProcessingMessage(data.message || "This is taking longer than usual. We'll email you when it's ready.")
        setIsLoading(false)
        pollJob(data.jobId)
        return
      }

      if (!res.ok) {
        setErrorMessage(data.error || 'Something went wrong. Please try again.')
        return
      }

      setValidation(data)
      setUpdatedAt(new Date())
      addHistoryEntry({ sessionId: data.sessionId, idea: payload.idea, targetCustomer: payload.targetCustomer })
    } catch {
      setErrorMessage('Could not reach the server. Please try again.')
    } finally {
      setIsLoading(false)
      setCooldown(true)
      setTimeout(() => setCooldown(false), SUBMIT_COOLDOWN_MS)
    }
  }

  async function pollJob(jobId) {
    const POLL_INTERVAL_MS = 4000
    const MAX_POLLS = 45 // ~3 minutes

    for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
      try {
        const res = await fetch(`${API_URL}/validate/status/${jobId}`)
        const data = await res.json()

        if (data.status === 'complete') {
          const { status: _status, ...result } = data
          setValidation(result)
          setUpdatedAt(new Date())
          setProcessingMessage('')
          addHistoryEntry({
            sessionId: result.sessionId,
            idea: lastSubmission?.idea,
            targetCustomer: lastSubmission?.targetCustomer,
          })
          return
        }

        if (data.status === 'failed') {
          setErrorMessage(data.error || 'The analysis failed while running in the background.')
          setProcessingMessage('')
          return
        }
        // status === 'processing' - keep polling
      } catch {
        // A transient network hiccup while polling shouldn't abandon the
        // job - it's still running server-side and the email will still
        // arrive; just try again next interval.
      }
    }

    setProcessingMessage('Still working on this in the background - check your email for the finished report.')
  }

  // Resumes a session picked from HistoryPanel, reusing the same
  // GET /reports/{sessionId} + adaptReportToValidation path as the
  // ?session= email-link flow above.
  async function openHistorySession(sessionId) {
    setErrorMessage('')
    setView('form')
    try {
      const res = await fetch(`${API_URL}/reports/${sessionId}`)
      if (!res.ok) {
        setErrorMessage('That session has expired or could not be found.')
        return
      }
      const report = await res.json()
      setValidation(adaptReportToValidation(report))
      setUpdatedAt(report.generatedAt ? new Date(report.generatedAt) : new Date())
    } catch {
      setErrorMessage('Could not reach the server. Please try again.')
    }
  }

  if (view === 'landing') {
    return (
      <LandingPage
        onStart={() => setView('form')}
        currentUser={currentUser}
        onSignIn={() => {
          setPreAuthView('landing')
          setView('account')
        }}
        onSignOut={handleSignOut}
      />
    )
  }

  // History/Compare/Analytics are account-only (no nav button reaches them
  // while signed out) - this only matters for the edge case of signing out
  // while already on one of these screens, so it doesn't hang around
  // showing a signed-in-only view to a now-signed-out user.
  if (['compare', 'history', 'analytics'].includes(view) && !currentUser) {
    return (
      <LandingPage
        onStart={() => setView('form')}
        currentUser={currentUser}
        onSignIn={() => {
          setPreAuthView('landing')
          setView('account')
        }}
        onSignOut={handleSignOut}
      />
    )
  }

  if (view === 'compare') {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <CompareIdeas apiUrl={API_URL} onBack={() => setView('form')} />
      </div>
    )
  }

  if (view === 'history') {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <HistoryPanel apiUrl={API_URL} token={authToken} onBack={() => setView('form')} onOpen={openHistorySession} />
      </div>
    )
  }

  if (view === 'analytics') {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <AnalyticsDashboard apiUrl={API_URL} token={authToken} onBack={() => setView('form')} />
      </div>
    )
  }

  if (view === 'account') {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <AuthPanel apiUrl={API_URL} onAuthenticated={handleAuthenticated} onBack={() => setView(preAuthView)} />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-10 sm:pt-14">
        <div className="mx-auto max-w-3xl">
          <div className="mb-8 flex items-center justify-between">
            <p className="font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
              Multi-agent · Live Web Search
            </p>
            <div className="flex items-center gap-2">
              {currentUser && (
                <>
                  <button
                    type="button"
                    onClick={() => setView('history')}
                    className="rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
                  >
                    History
                  </button>
                  <button
                    type="button"
                    onClick={() => setView('compare')}
                    className="rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
                  >
                    Compare ideas
                  </button>
                  <button
                    type="button"
                    onClick={() => setView('analytics')}
                    className="rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
                  >
                    Analytics
                  </button>
                </>
              )}
              {currentUser ? (
                <button
                  type="button"
                  onClick={handleSignOut}
                  title={`Signed in as ${currentUser.email} - click to sign out`}
                  className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
                >
                  <IconUser className="h-3 w-3 text-accent" />
                  <span className="max-w-[9rem] truncate normal-case">{currentUser.email}</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setPreAuthView('form')
                    setView('account')
                  }}
                  className="rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
                >
                  Sign in
                </button>
              )}
              <span className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-accent">
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
                Live
              </span>
            </div>
          </div>

          <header className="mb-8">
            <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
              Affinity
            </p>
            <h1 className="font-serif text-4xl leading-tight text-text sm:text-5xl">
              Before you build it,
              <br />
              measure the <em className="text-accent italic">affinity</em>.
            </h1>
            <p className="mt-3 font-mono text-xs uppercase tracking-widest text-muted">
              AI Market Research Agent
            </p>
          </header>

          <IdeaForm onSubmit={validateIdea} isLoading={isLoading} loadingStep={loadingStep} disabled={cooldown} />

          {errorMessage && (
            <ErrorState
              message={errorMessage}
              onRetry={lastSubmission ? () => validateIdea(lastSubmission) : undefined}
            />
          )}

          {processingMessage && !validation && (
            <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-accent/30 bg-accent/5 p-4 text-sm text-text">
              <span className="pulse-dot mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span>{processingMessage}</span>
            </div>
          )}

          {validation && (validation.results?.length ?? 0) === 0 && <EmptyState />}
        </div>

        {validation && (
          <>
            <ValidationResults
              summary={validation.summary}
              results={validation.results ?? []}
              marketOpportunity={validation.marketOpportunity}
              competitors={validation.competitors}
              whiteSpace={validation.whiteSpace}
              swot={validation.swot}
              mvp={validation.mvp}
              gtm={validation.gtm}
              confidence={validation.confidence}
              contradictions={validation.contradictions}
              experiments={validation.experiments}
              actionPlan={validation.actionPlan}
              sessionId={validation.sessionId}
              apiUrl={API_URL}
              errors={validation.errors}
            />
            <p className="mx-auto mt-10 max-w-5xl border-t border-border pt-4 text-center font-mono text-xs uppercase tracking-wider text-muted">
              Sources: {sourceCount} · Multi-agent Pipeline · Live Web Search
              {updatedAt && (
                <>
                  {' '}
                  ·{' '}
                  <span className="text-accent">
                    Last updated: {updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </>
              )}
            </p>
          </>
        )}
      </main>
    </div>
  )
}
