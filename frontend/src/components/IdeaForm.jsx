import { useState } from 'react'

export default function IdeaForm({ onSubmit, isLoading, loadingStep }) {
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
      className="rounded-2xl border border-border bg-panel p-6 sm:p-8"
    >
      <div className="space-y-5">
        <div>
          <label htmlFor="idea" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
            Startup idea
          </label>
          <textarea
            id="idea"
            rows={3}
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
          <label htmlFor="targetCustomer" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
            Target customer
          </label>
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
          <label htmlFor="problem" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
            Problem being solved
          </label>
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
          disabled={isLoading}
          className="w-full rounded-full bg-accent px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-surface transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? 'Validating…' : 'Validate idea'}
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
