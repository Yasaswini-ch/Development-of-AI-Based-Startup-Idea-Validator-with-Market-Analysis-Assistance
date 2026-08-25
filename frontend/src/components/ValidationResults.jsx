export default function ValidationResults({ summary, results }) {
  return (
    <div className="mt-6">
      <div className="rounded-2xl border border-border bg-panel p-6 sm:p-8">
        <h2 className="text-lg font-semibold text-text mb-2">Validation summary</h2>
        <p className="text-sm text-muted leading-relaxed">{summary}</p>
      </div>

      {results.length > 0 && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {results.map((r, i) => (
            <a
              key={i}
              href={r.url}
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-border bg-panel p-4 transition-colors hover:border-accent"
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <h3 className="text-sm font-medium text-text line-clamp-2">{r.title}</h3>
                {typeof r.score === 'number' && (
                  <span className="shrink-0 rounded-full bg-accent/15 px-2 py-0.5 text-xs font-medium text-accent">
                    {Math.round(r.score * 100)}%
                  </span>
                )}
              </div>
              <p className="text-sm text-muted leading-relaxed line-clamp-3">{r.snippet}</p>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
