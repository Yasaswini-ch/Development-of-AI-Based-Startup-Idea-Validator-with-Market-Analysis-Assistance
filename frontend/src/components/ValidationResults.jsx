import { useState } from 'react'
import useCountUp from '../hooks/useCountUp'

const INITIAL_VISIBLE = 3

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

function ScoreBadge({ score }) {
  const percent = useCountUp(Math.round(score * 100), 500)
  return (
    <span className="shrink-0 rounded border border-border px-1.5 py-0.5 font-mono text-[11px] tracking-wide text-muted">
      {percent}%
    </span>
  )
}

function ResultCard({ r }) {
  return (
    <a
      href={r.url}
      target="_blank"
      rel="noreferrer"
      className="block rounded-xl border border-border bg-panel p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:shadow-lg hover:shadow-black/30"
    >
      <div className="flex items-start justify-between gap-3 mb-1.5">
        <h3 className="text-sm font-medium text-text line-clamp-2">{r.title}</h3>
        {typeof r.score === 'number' && <ScoreBadge score={r.score} />}
      </div>
      <p className="text-sm text-muted leading-relaxed line-clamp-3">{r.snippet}</p>
      <p className="mt-2 truncate font-mono text-[11px] uppercase tracking-wide text-muted/60">
        {hostnameOf(r.url)}
      </p>
    </a>
  )
}

function AngleGroup({ angle, items }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? items : items.slice(0, INITIAL_VISIBLE)

  return (
    <div>
      <h3 className="mb-3 font-mono text-xs uppercase tracking-widest text-muted">{angle}</h3>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((r, i) => (
          <ResultCard key={r.url || i} r={r} />
        ))}
      </div>
      {items.length > INITIAL_VISIBLE && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-3 font-mono text-xs uppercase tracking-wide text-accent hover:text-accent-hover"
        >
          {expanded ? 'Show less' : `Show ${items.length - INITIAL_VISIBLE} more`}
        </button>
      )}
    </div>
  )
}

export default function ValidationResults({ summary, results }) {
  const groups = []
  const order = []
  for (const r of results) {
    const key = r.angle || 'Sources'
    if (!order.includes(key)) order.push(key)
  }
  for (const key of order) {
    groups.push({ angle: key, items: results.filter((r) => (r.angle || 'Sources') === key) })
  }

  return (
    <div className="mt-6">
      <div className="mx-auto max-w-xl rounded-2xl border border-border bg-panel p-6 sm:p-8">
        <h2 className="mb-2 font-mono text-xs uppercase tracking-widest text-muted">
          Validation summary
        </h2>
        <p className="text-sm text-text leading-relaxed">{summary}</p>
      </div>

      <div className="mt-8 space-y-8">
        {groups.map((g) => (
          <AngleGroup key={g.angle} angle={g.angle} items={g.items} />
        ))}
      </div>
    </div>
  )
}
