import { useEffect, useState } from 'react'
import IdeaForm from './components/IdeaForm'
import ValidationResults from './components/ValidationResults'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'
import LandingPage from './components/LandingPage'
import CompareIdeas from './components/CompareIdeas'
import HistoryPanel from './components/HistoryPanel'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import PlatformHealth from './components/PlatformHealth'
import AuthPanel from './components/AuthPanel'
import DeepAnalysisPrompt from './components/DeepAnalysisPrompt'
import AccountMenu from './components/AccountMenu'
import useCountUp from './hooks/useCountUp'
import useLoadingSteps from './hooks/useLoadingSteps'
import { addHistoryEntry, clearHistory } from './lib/history'
import { clearCompareList } from './lib/compareList'
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
    whiteSpace: report.whiteSpace,
    swot: report.swot,
    mvp: report.mvp,
    gtm: report.gtm,
    marketViability: report.marketViability,
    confidence: report.confidence,
    contradictions: report.contradictions,
    experiments: report.experiments,
    actionPlan: report.actionPlan,
    assumptions: report.assumptions,
    revenueModels: report.revenueModels,
    verdict: report.verdict,
    sessionId: report.sessionId,
    errors: report.sectionErrors || {},
  }
}

export default function App() {
  const [persisted] = useState(loadPersisted)
  // Arriving from a password-reset email (?reset=<token>): remember the token
  // and take it out of the address bar and browser history straight away.
  const [resetToken] = useState(() => {
    try {
      const token = new URLSearchParams(window.location.search).get('reset')
      if (token) window.history.replaceState({}, '', window.location.pathname)
      return token
    } catch {
      return null
    }
  })
  // Skip the landing page when a session is already mid-flow (a persisted
  // result from before a tab reload, per loadPersisted's own reasoning) -
  // it should only greet a genuinely fresh visitor, not interrupt someone
  // returning to their own results.
  const [view, setView] = useState(resetToken ? 'account' : persisted?.validation ? 'form' : 'landing')
  const [isLoading, setIsLoading] = useState(false)
  // The button already disables mid-request, but re-enables the instant a
  // response lands - nothing stopped someone from immediately firing another
  // request right after, which is exactly the kind of burst that exhausts
  // the shared Groq quota fastest. A short cooldown after each request
  // finishes (success or failure) spaces that out.
  const [cooldown, setCooldown] = useState(false)
  const [validation, setValidation] = useState(persisted?.validation ?? null)
  // The idea typed into the landing hero, carried into the form (see IdeaForm's `initial`).
  const [prefill, setPrefill] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [processingMessage, setProcessingMessage] = useState('')
  const [deepAnalysisMessage, setDeepAnalysisMessage] = useState('')
  const [lastSubmission, setLastSubmission] = useState(persisted?.lastSubmission ?? null)
  const [updatedAt, setUpdatedAt] = useState(persisted?.updatedAt ?? null)
  const [authToken, setAuthToken] = useState(getToken)
  const [currentUser, setCurrentUser] = useState(getStoredUser)
  // Remembers where "Sign in" was opened from (landing vs. the main form)
  // purely so its own "Back" button returns there instead of always
  // dropping onto the form - cosmetic, not auth state.
  const [preAuthView, setPreAuthView] = useState('form')
  const loadingProgress = useLoadingSteps(isLoading)
  const sourceCount = useCountUp(validation?.results?.length ?? 0)

  // The signed-in user object login()/signup() return has just {id, email} -
  // fields like isAdmin only come from a live GET /auth/me lookup - so any
  // place that sets currentUser from an auth response needs to follow up
  // with this to get the real, current value rather than leaving isAdmin
  // permanently undefined until an unrelated full page reload happens to
  // trigger the mount effect below.
  function refreshCurrentUser(token) {
    return fetch(`${API_URL}/auth/me`, { headers: authHeaders(token) })
      .then((res) => {
        if (res.ok) return res.json().then((user) => setCurrentUser(user))
        if (res.status === 401) {
          clearAuth()
          setAuthToken(null)
          setCurrentUser(null)
          setValidation(null)
          setLastSubmission(null)
          setUpdatedAt(null)
          try {
            sessionStorage.removeItem(STORAGE_KEY)
          } catch {}
        }
      })
      .catch(() => {
        // Network-level failure, not a server-confirmed invalid token -
        // nothing to do; the cached credentials stay as they were.
      })
  }

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
          setValidation(null)
          setLastSubmission(null)
          setUpdatedAt(null)
          try {
            sessionStorage.removeItem(STORAGE_KEY)
          } catch {}
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
    // A validation run anonymously, then signed into right after, would
    // otherwise be stuck in this browser's device-local history forever -
    // claim it onto the new account before the guest state below gets wiped,
    // so it shows up in GET /me/history like anything else on this account.
    // Best-effort: a signed-in account's own validations from other
    // sessions aren't affected either way, so a failed claim here isn't
    // worth surfacing as an error.
    if (!authToken && validation?.sessionId) {
      fetch(`${API_URL}/me/claim-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
        body: JSON.stringify({ sessionId: validation.sessionId }),
      }).catch(() => {})
    }
    setAuth({ token, user })
    setAuthToken(token)
    setCurrentUser(user)
    setValidation(null)
    setLastSubmission(null)
    setUpdatedAt(null)
    setErrorMessage('')
    setProcessingMessage('')
    setDeepAnalysisMessage('')
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {}
    // lib/history.js and lib/compareList.js are device-local (localStorage),
    // not per-user - on a shared computer, whatever the previous, possibly
    // signed-out visitor validated was still sitting there and would show
    // up in this account's History/Compare screens the moment they signed
    // in. This account's own validations live server-side (GET
    // /me/history) once signed in, so the local lists have nothing this
    // account needs preserved.
    clearHistory()
    clearCompareList()
    setView('form')
    // Signing in doesn't remount App, so the mount effect above never
    // reruns for this token - without this, isAdmin (and anything else
    // /auth/me adds beyond {id, email}) would stay unset until an unrelated
    // full page reload happened to trigger it.
    refreshCurrentUser(token)
  }

  function handleSignOut() {
    clearAuth()
    setAuthToken(null)
    setCurrentUser(null)
    setValidation(null)
    setLastSubmission(null)
    setUpdatedAt(null)
    setErrorMessage('')
    setProcessingMessage('')
    setDeepAnalysisMessage('')
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {}
    // Same reasoning as handleAuthenticated: don't leave this account's
    // validations sitting in the device-local History/Compare lists for
    // the next, possibly different, person to sign in (or stay signed out)
    // on this same browser and see them.
    clearHistory()
    clearCompareList()
    setView('landing')
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
        // Signed-in accounts already get this recorded server-side (see
        // /reports/{id} + GET /me/history) - only anonymous visits need the
        // device-local fallback list.
        if (!authToken) {
          addHistoryEntry({
            sessionId,
            idea: report.ideaSummary?.idea,
            targetCustomer: report.ideaSummary?.targetCustomer,
          })
        }
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
    setDeepAnalysisMessage('')

    try {
      const res = await fetch(`${API_URL}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders(authToken) },
        body: JSON.stringify(payload),
      })
      const data = await res.json()

      if (data.needsEmailForDeepAnalysis) {
        // Every cloud model was exhausted for this idea and no email was on
        // file yet to route the slower local-model retry through - ask for
        // one instead of silently showing the weaker deterministic result.
        setDeepAnalysisMessage(data.message || 'This idea needs deeper analysis. Enter your email to continue.')
        setIsLoading(false)
        return
      }

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
        let msg = data.error
        if (!msg && data.detail) {
          if (Array.isArray(data.detail)) {
            msg = data.detail.map((d) => d.msg || `${d.loc?.join('.')}: ${d.type}`).join(', ')
          } else {
            msg = String(data.detail)
          }
        }
        setErrorMessage(msg || 'Something went wrong. Please try again.')
        return
      }

      setValidation(data)
      setUpdatedAt(new Date())
      // Signed-in accounts already get this recorded server-side; only
      // anonymous visits need the device-local fallback list (see
      // lib/history.js) - writing it either way is what let one signed-in
      // account's validations leak into the next, possibly different,
      // person's device-local History screen.
      if (!authToken) {
        addHistoryEntry({ sessionId: data.sessionId, idea: payload.idea, targetCustomer: payload.targetCustomer })
      }
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
          if (!authToken) {
            addHistoryEntry({
              sessionId: result.sessionId,
              idea: lastSubmission?.idea,
              targetCustomer: lastSubmission?.targetCustomer,
            })
          }
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
        onStart={(idea) => {
          if (idea) setPrefill({ idea, key: Date.now() })
          setView('form')
        }}
        currentUser={currentUser}
        onSignIn={() => {
          setPreAuthView('landing')
          setView('account')
        }}
        onSignOut={handleSignOut}
        apiUrl={API_URL}
        onAuthenticated={handleAuthenticated}
      />
    )
  }

  // History/Compare/Analytics/Platform Health are account-only (no nav
  // button reaches them while signed out) - this only matters for the edge
  // case of signing out while already on one of these screens, so it
  // doesn't hang around showing a signed-in-only view to a now-signed-out
  // user.
  if (['compare', 'history', 'analytics', 'platform-health'].includes(view) && !currentUser) {
    return (
      <LandingPage
        onStart={() => setView('form')}
        currentUser={currentUser}
        onSignIn={() => {
          setPreAuthView('landing')
          setView('account')
        }}
        onSignOut={handleSignOut}
        apiUrl={API_URL}
        onAuthenticated={handleAuthenticated}
      />
    )
  }

  // Platform Health is admin-only, not just account-only - a signed-in
  // non-admin who lands here (e.g. by navigating back to a stale URL/state)
  // gets bounced the same way a signed-out user does above, rather than
  // reaching a component that would just render a 403 from the API.
  if (view === 'platform-health' && !currentUser?.isAdmin) {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <div className="mx-auto max-w-md rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">
          Admin access required.
          <button
            type="button"
            onClick={() => setView('form')}
            className="mx-auto mt-4 block rounded-full border border-border bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
          >
            Back
          </button>
        </div>
      </div>
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
        <HistoryPanel
          apiUrl={API_URL}
          token={authToken}
          onBack={() => setView('form')}
          onOpen={openHistorySession}
          onGoToCompare={() => setView('compare')}
        />
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

  if (view === 'platform-health') {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <PlatformHealth apiUrl={API_URL} token={authToken} onBack={() => setView('form')} />
      </div>
    )
  }

  if (view === 'account') {
    return (
      <div className="min-h-screen bg-surface px-4 py-10">
        <AuthPanel apiUrl={API_URL} onAuthenticated={handleAuthenticated} onBack={() => setView(preAuthView)} resetToken={resetToken} />
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
              {currentUser ? (
                <AccountMenu currentUser={currentUser} onNavigate={setView} onSignOut={handleSignOut} />
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
              <span className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-info">
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-info" />
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

          <IdeaForm key={prefill?.key ?? 'blank'} initial={prefill} onSubmit={validateIdea} isLoading={isLoading} loadingProgress={loadingProgress} disabled={cooldown} />

          {deepAnalysisMessage && (
            <DeepAnalysisPrompt
              message={deepAnalysisMessage}
              defaultEmail={currentUser?.email ?? ''}
              onSubmit={(email) => validateIdea({ ...lastSubmission, email })}
            />
          )}

          {errorMessage && (
            <ErrorState
              message={errorMessage}
              onRetry={lastSubmission ? () => validateIdea(lastSubmission) : undefined}
            />
          )}

          {processingMessage && !validation && (
            <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-info/30 bg-info/5 p-4 text-sm text-text">
              <span className="pulse-dot mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-info" />
              <span>{processingMessage}</span>
            </div>
          )}

          {validation && (validation.results?.length ?? 0) === 0 && <EmptyState />}
        </div>

        {validation && (
          <>
            <ValidationResults
              idea={lastSubmission?.idea}
              targetCustomer={lastSubmission?.targetCustomer}
              problem={lastSubmission?.problem}
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
              assumptions={validation.assumptions}
              revenueModels={validation.revenueModels}
              verdict={validation.verdict}
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
