import { useState } from 'react'
import IdeaForm from './components/IdeaForm'
import ValidationResults from './components/ValidationResults'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'
import useCountUp from './hooks/useCountUp'
import useLoadingSteps from './hooks/useLoadingSteps'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [isLoading, setIsLoading] = useState(false)
  const [validation, setValidation] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [lastSubmission, setLastSubmission] = useState(null)
  const loadingStep = useLoadingSteps(isLoading)
  const sourceCount = useCountUp(validation?.results.length ?? 0)

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
    } catch {
      setErrorMessage('Could not reach the server. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-12 sm:pt-16">
        <div className="mx-auto max-w-xl">
          <header className="mb-8 text-center">
            <p className="mb-3 font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
              Multi-agent · Live Web Search
            </p>
            <h1 className="text-3xl font-semibold text-text sm:text-4xl">
              AI Startup Idea Validator
            </h1>
            <p className="mt-2 text-sm text-muted">Market analysis assistance, in seconds.</p>
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
            <ValidationResults summary={validation.summary} results={validation.results} />
            <p className="mx-auto mt-10 max-w-xl border-t border-border pt-4 text-center font-mono text-xs uppercase tracking-wider text-muted">
              Sources: {sourceCount} · Multi-agent Pipeline · Live Web Search
            </p>
          </>
        )}
      </main>
    </div>
  )
}
