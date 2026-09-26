import { useState } from 'react'
import { IconLightbulb, IconUsers, IconAlertTriangle, IconCheckCircle } from './icons'
import { assessIdeaClarity } from '../lib/ideaClarity'

const IDEA_MAX = 2000

function LoadingSteps({ phases, currentIndex }) {
  return (
    <ul className="space-y-1.5 rounded-lg border border-border bg-surface px-3.5 py-3">
      {phases.map((phase, i) => {
        const done = i < currentIndex
        const active = i === currentIndex
        return (
          <li
            key={phase}
            className={`flex items-center gap-2 font-mono text-xs uppercase tracking-wide transition-colors ${
              done ? 'text-success' : active ? 'text-info' : 'text-muted/50'
            }`}
          >
            {done ? (
              <IconCheckCircle className="h-3.5 w-3.5 shrink-0" />
            ) : (
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? 'pulse-dot bg-info' : 'bg-muted/30'}`}
              />
            )}
            <span className={active ? 'cursor-blink' : ''}>{phase}</span>
          </li>
        )
      })}
    </ul>
  )
}

export default function IdeaForm({ onSubmit, isLoading, loadingProgress, disabled }) {
  const [idea, setIdea] = useState('')
  const [targetCustomer, setTargetCustomer] = useState('')
  const [problem, setProblem] = useState('')
  const [error, setError] = useState('')
  const [errorField, setErrorField] = useState('')
  // A vague idea gets flagged, not blocked - the founder can submit anyway
  // by clicking again. Prevents spending a research pass and several LLM
  // calls on a pitch too thin to ground the analysis in.
  const [clarityWarning, setClarityWarning] = useState(null)

  function handleSubmit(e) {
    e.preventDefault()
    if (!idea.trim()) {
      setError('Please describe your startup idea before validating.')
      setErrorField('idea')
      return
    }
    if (!targetCustomer.trim()) {
      setError('Please describe your target customer before validating.')
      setErrorField('targetCustomer')
      return
    }
    if (!problem.trim()) {
      setError('Please describe the problem being solved before validating.')
      setErrorField('problem')
      return
    }
    setError('')
    setErrorField('')

    if (!clarityWarning) {
      const clarity = assessIdeaClarity(idea)
      if (!clarity.clear) {
        setClarityWarning(clarity.reason)
        return
      }
    }
    setClarityWarning(null)
    onSubmit({ idea, targetCustomer, problem, email: '' })
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
              {idea.trim() && <IconCheckCircle className="h-4 w-4 text-success" />}
            </span>
          </div>
          <textarea
            id="idea"
            rows={10}
            maxLength={IDEA_MAX}
            value={idea}
            onChange={(e) => {
              setIdea(e.target.value)
              if (clarityWarning) setClarityWarning(null)
            }}
            placeholder="Describe your startup concept in as much detail as you'd like — the core workflow, target customer pain, monetization mechanism, key assumptions, competitors you're aware of, anything that helps the research agents dig deeper."
            className={`w-full resize-y rounded-lg bg-surface border px-3.5 py-3 text-sm leading-relaxed text-text placeholder:text-muted outline-none transition-colors focus:border-accent ${
              errorField === 'idea' ? 'border-danger' : 'border-border'
            }`}
          />
          {errorField === 'idea' && <p className="mt-1.5 text-sm text-danger">{error}</p>}
          {clarityWarning && (
            <div className="mt-1.5 flex items-start gap-2 rounded-lg border border-accent/30 bg-accent/5 px-3 py-2.5 text-sm text-text">
              <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
              <p>
                {clarityWarning} <span className="text-muted">Submit again to validate as written.</span>
              </p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label htmlFor="targetCustomer" className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
                <IconUsers className="h-3.5 w-3.5 text-accent" />
                Target customer <span className="text-accent">*</span>
              </label>
              {targetCustomer.trim() && <IconCheckCircle className="h-4 w-4 text-success" />}
            </div>
            <input
              id="targetCustomer"
              type="text"
              value={targetCustomer}
              onChange={(e) => setTargetCustomer(e.target.value)}
              placeholder="e.g. In-house General Counsels at mid-market SaaS"
              className={`w-full rounded-lg bg-surface border px-3.5 py-2.5 text-sm text-text placeholder:text-muted outline-none transition-colors focus:border-accent ${
                errorField === 'targetCustomer' ? 'border-danger' : 'border-border'
              }`}
            />
            {errorField === 'targetCustomer' && <p className="mt-1.5 text-sm text-danger">{error}</p>}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label htmlFor="problem" className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
                <IconAlertTriangle className="h-3.5 w-3.5 text-accent" />
                Problem being solved <span className="text-accent">*</span>
              </label>
              {problem.trim() && <IconCheckCircle className="h-4 w-4 text-success" />}
            </div>
            <input
              id="problem"
              type="text"
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="What painful problem does this startup solve?"
              className={`w-full rounded-lg bg-surface border px-3.5 py-2.5 text-sm text-text placeholder:text-muted outline-none transition-colors focus:border-accent ${
                errorField === 'problem' ? 'border-danger' : 'border-border'
              }`}
            />
            {errorField === 'problem' && <p className="mt-1.5 text-sm text-danger">{error}</p>}
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading || disabled}
          className="w-full rounded-full bg-accent px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? 'Validating…' : disabled ? 'One moment…' : 'Validate startup idea →'}
        </button>

        {isLoading && <LoadingSteps phases={loadingProgress.phases} currentIndex={loadingProgress.currentIndex} />}
      </div>
    </form>
  )
}
