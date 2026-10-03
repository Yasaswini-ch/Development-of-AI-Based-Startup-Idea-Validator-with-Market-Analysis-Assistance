import { useState } from 'react'
import { AGENTS } from './agentsData'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'ai', label: 'AI agents' },
  { key: 'rules', label: 'Rule-based' },
]

export default function AgentsGrid() {
  const [filter, setFilter] = useState('all')
  const aiCount = AGENTS.filter((a) => a.kind === 'ai').length
  const rulesCount = AGENTS.length - aiCount
  const shown = filter === 'all' ? AGENTS : AGENTS.filter((a) => a.kind === filter)

  return (
    <section id="agents" className="mt-16 scroll-mt-24" aria-labelledby="agents-heading">
      <p className="mb-2 text-center font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">The team behind your report</p>
      <h2 id="agents-heading" className="mb-3 text-center font-serif text-2xl font-semibold text-text sm:text-3xl">
        {AGENTS.length} agents and engines. One evidence trail.
      </h2>
      <p className="mx-auto mb-6 max-w-2xl text-center text-sm leading-relaxed text-muted">
        {aiCount} AI agents reason over what was found. {rulesCount} rule-based engines score and check it with plain code,
        so the numbers do not depend on a language model.
      </p>

      <div role="group" aria-label="Filter agents" className="mb-5 flex justify-center gap-2">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
            className={`rounded-full border px-3.5 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${
              filter === key
                ? 'border-accent bg-accent text-white'
                : 'border-border bg-panel text-muted-strong hover:border-accent/50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map(({ name, kind, Icon, body, tools }) => (
          <div
            key={name}
            className="rounded-2xl border border-border bg-panel p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/50"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/10 text-accent">
                <Icon className="h-4 w-4" />
              </span>
              <span
                className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${
                  kind === 'ai'
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-border-strong bg-surface text-muted-strong'
                }`}
              >
                {kind === 'ai' ? 'AI agent' : 'Rule-based'}
              </span>
            </div>
            <h3 className="mt-3 font-serif text-base font-semibold text-text">{name}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
            {tools?.length > 0 && (
              <ul aria-label={`${name} tools`} className="mt-3 flex flex-wrap gap-1.5">
                {tools.map((t) => (
                  <li key={t} className="rounded border border-border-strong bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted-strong">
                    {t}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
