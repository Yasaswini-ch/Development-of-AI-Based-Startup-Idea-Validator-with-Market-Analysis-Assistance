import { useState } from 'react'
import IdeaForm from './components/IdeaForm'
import ValidationResults from './components/ValidationResults'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [isLoading, setIsLoading] = useState(false)
  const [validation, setValidation] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [lastSubmission, setLastSubmission] = useState(null)

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
      <main className="mx-auto max-w-xl px-4 py-16 sm:py-24">
        <header className="mb-8 text-center">
          <h1 className="text-3xl font-semibold text-text sm:text-4xl">
            AI Startup Idea Validator
          </h1>
          <p className="mt-2 text-sm text-muted">Market analysis assistance, in seconds.</p>
        </header>

        <IdeaForm onSubmit={validateIdea} isLoading={isLoading} />

        {errorMessage && (
          <ErrorState
            message={errorMessage}
            onRetry={lastSubmission ? () => validateIdea(lastSubmission) : undefined}
          />
        )}

        {validation && validation.results.length === 0 && <EmptyState />}

        {validation && validation.results.length > 0 && (
          <ValidationResults summary={validation.summary} results={validation.results} />
        )}
      </main>
    </div>
  )
}
