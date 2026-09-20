import { IconAlertTriangle, IconTrendingUp } from './icons'

function EmptyWhiteSpace() {
  return (
    <div className="flex flex-col items-center justify-center p-2 text-center">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">White-space analysis is still forming</p>
      <p className="mt-1 max-w-sm text-xs leading-snug text-muted">
        Run a validation with market and competitor results to surface opportunity gaps.
      </p>
    </div>
  )
}

export default function WhiteSpaceAnalysis({ data }) {
  const opportunities = data?.opportunities || []
  if (opportunities.length === 0) {
    return <EmptyWhiteSpace />
  }

  return (
    <div>
      <p className="text-sm leading-relaxed text-text">{data.summary}</p>
      {data.competitionNote && (
        <p className="mt-3 rounded-xl border border-border bg-surface p-3 text-sm leading-relaxed text-muted">
          {data.competitionNote}
        </p>
      )}

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {opportunities.map((item, index) => (
          <div key={index} className="rounded-xl border border-border bg-surface p-5">
            <h4 className="flex items-center gap-1.5 text-sm font-semibold text-text">
              <IconTrendingUp className="h-3.5 w-3.5 text-accent" />
              {item.title}
            </h4>
            <dl className="mt-3 space-y-3">
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Customer pain</dt>
                <dd className="mt-1 text-sm leading-relaxed text-text">{item.why}</dd>
              </div>
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Startup fit</dt>
                <dd className="mt-1 text-sm leading-relaxed text-text">{item.fit}</dd>
              </div>
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Evidence</dt>
                <dd className="mt-1 text-sm leading-relaxed text-muted">{item.evidence}</dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}
