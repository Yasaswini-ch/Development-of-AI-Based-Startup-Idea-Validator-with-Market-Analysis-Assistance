import { useEffect, useState } from 'react'
import IdeaForm from './components/IdeaForm'
import ValidationResults from './components/ValidationResults'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'
import useCountUp from './hooks/useCountUp'
import useLoadingSteps from './hooks/useLoadingSteps'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const STORAGE_KEY = 'affinity:lastValidation'

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

export default function App() {
  const [persisted] = useState(loadPersisted)
  const [isLoading, setIsLoading] = useState(false)
  const [validation, setValidation] = useState(persisted?.validation ?? null)
  const [errorMessage, setErrorMessage] = useState('')
  const [lastSubmission, setLastSubmission] = useState(persisted?.lastSubmission ?? null)
  const [updatedAt, setUpdatedAt] = useState(persisted?.updatedAt ?? null)
  const loadingStep = useLoadingSteps(isLoading)
  const sourceCount = useCountUp(validation?.results.length ?? 0)

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

  async function validateIdea(payload) {
    setIsLoading(true)
    setErrorMessage('')
    setValidation(null)
    setLastSubmission(payload)

    try {
      const res = await fetch(`${API_URL}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()

      if (!res.ok) {
        setErrorMessage(data.error || 'Something went wrong. Please try again.')
        return
      }

      setValidation(data)
      setUpdatedAt(new Date())
    } catch {
      setErrorMessage('Could not reach the server. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-10 sm:pt-14">
        <div className="mx-auto max-w-xl">
          <div className="mb-8 flex items-center justify-between">
            <p className="font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
              Multi-agent · Live Web Search
            </p>
            <span className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-accent">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
              Live
            </span>
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

          <IdeaForm onSubmit={validateIdea} isLoading={isLoading} loadingStep={loadingStep} />

          {errorMessage && (
            <ErrorState
              message={errorMessage}
              onRetry={lastSubmission ? () => validateIdea(lastSubmission) : undefined}
            />
          )}

          {validation && validation.results.length === 0 && <EmptyState />}
        </div>

        {validation && validation.results.length > 0 && (
          <>
            <ValidationResults
              summary={validation.summary}
              results={validation.results}
              marketOpportunity={validation.marketOpportunity}
              competitors={validation.competitors}
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
