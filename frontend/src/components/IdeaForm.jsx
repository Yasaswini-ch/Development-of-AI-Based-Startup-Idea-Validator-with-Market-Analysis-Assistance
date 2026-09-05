import { useState } from 'react'
import { IconLightbulb, IconUsers, IconAlertTriangle, IconCheckCircle } from './icons'

const IDEA_MAX = 300

export default function IdeaForm({ onSubmit, isLoading, loadingStep, disabled }) {
  const [idea, setIdea] = useState('')
  const [targetCustomer, setTargetCustomer] = useState('')
  const [problem, setProblem] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!idea.trim()) {
      setError('Please describe your startup idea before validating.')
      return
    }
    setError('')
    onSubmit({ idea, targetCustomer, problem })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8"
    >
      <div className="space-y-5">
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label htmlFor="idea" className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <IconLightbulb className="h-3.5 w-3.5 text-accent" />
              Startup idea <span className="text-accent">*</span>
            </label>
            <span className="flex items-center gap-2 font-mono text-[11px] text-muted">
              {idea.length} / {IDEA_MAX}
              {idea.trim() && <IconCheckCircle className="h-4 w-4 text-accent" />}
            </span>
          </div>
          <textarea
            id="idea"
            rows={3}
            maxLength={IDEA_MAX}
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="An AI tool that validates business ideas using market data"
            className={`w-full rounded-lg bg-surface border px-3.5 py-2.5 text-sm text-text placeholder:text-muted outline-none transition-colors focus:border-accent ${
              error ? 'border-danger' : 'border-border'
            }`}
          />
          {error && <p className="mt-1.5 text-sm text-danger">{error}</p>}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label htmlFor="targetCustomer" className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <IconUsers className="h-3.5 w-3.5 text-accent" />
              Target customer
            </label>
            {targetCustomer.trim() && <IconCheckCircle className="h-4 w-4 text-accent" />}
          </div>
          <input
            id="targetCustomer"
            type="text"
            value={targetCustomer}
            onChange={(e) => setTargetCustomer(e.target.value)}
            placeholder="Early-stage founders"
            className="w-full rounded-lg bg-surface border border-border px-3.5 py-2.5 text-sm text-text placeholder:text-muted outline-none transition-colors focus:border-accent"
          />
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label htmlFor="problem" className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <IconAlertTriangle className="h-3.5 w-3.5 text-accent" />
              Problem being solved
            </label>
            {problem.trim() && <IconCheckCircle className="h-4 w-4 text-accent" />}
          </div>
          <textarea
            id="problem"
            rows={2}
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            placeholder="What painful problem does this startup solve?"
            className="w-full rounded-lg bg-surface border border-border px-3.5 py-2.5 text-sm text-text placeholder:text-muted outline-none transition-colors focus:border-accent"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || disabled}
          className="w-full rounded-full bg-accent px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? 'Validating…' : disabled ? 'One moment…' : 'Validate idea'}
        </button>

        {isLoading && (
          <p className="text-center font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
            {loadingStep}
          </p>
        )}
      </div>
    </form>
  )
}
