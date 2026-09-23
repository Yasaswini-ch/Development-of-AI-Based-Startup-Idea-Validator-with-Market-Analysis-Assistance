import { useState } from 'react'
import { IconAlertTriangle } from './icons'

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

// Shown instead of a normal result when every cloud model was exhausted for
// this request (backend/agent/llm.py's NeedsDeepAnalysisError) - rather than
// silently serving the weaker deterministic-fallback result, main.py asks
// for an email so the (much slower) local-model retry can run in the
// background and email the report when it's ready.
export default function DeepAnalysisPrompt({ message, onSubmit, defaultEmail = '' }) {
  const [email, setEmail] = useState(defaultEmail)
  const [error, setError] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    if (!EMAIL_PATTERN.test(email.trim())) {
      setError('Please enter a valid email address.')
      return
    }
    setError('')
    onSubmit(email.trim())
    setSubmitted(true)
  }

  if (submitted) {
    return (
      <div className="mt-4 rounded-xl border-2 border-success/40 bg-success/5 p-5">
        <div className="flex items-center gap-2.5">
          <span className="text-success">✓</span>
          <p className="text-sm leading-relaxed text-text">
            Submitted — we'll send the full report to <strong>{email}</strong> when it's ready.
          </p>
        </div>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-4 rounded-xl border-2 border-info/40 bg-info/5 p-5"
    >
      <div className="flex items-start gap-2.5">
        <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-sm leading-relaxed text-text">{message}</p>
      </div>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-info"
        />
        <button
          type="submit"
          className="shrink-0 rounded-full bg-info px-5 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-info-hover"
        >
          Send me the report
        </button>
      </div>
      {error && <p className="mt-1.5 text-sm text-danger">{error}</p>}
    </form>
  )
}
