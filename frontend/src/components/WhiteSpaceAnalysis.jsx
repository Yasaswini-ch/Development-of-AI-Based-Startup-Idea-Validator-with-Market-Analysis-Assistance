import { IconAlertTriangle, IconTrendingUp } from './icons'

// Mirrors backend/agent/white_space.py's _source_evidence fallback exactly -
// used only to tell a real quoted source snippet apart from "no snippet was
// available" visually, never to alter what's shown.
const _GENERIC_EVIDENCE = 'Grounded in the retrieved market sources.'

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
        {opportunities.map((item, index) => {
          const isGenericEvidence = !item.evidence || item.evidence === _GENERIC_EVIDENCE
          return (
            <div
              key={index}
              className={`rounded-xl border-[1.5px] bg-surface p-5 ${isGenericEvidence ? 'border-border-strong' : 'border-success/50'}`}
            >
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <p className="font-mono text-[10px] uppercase tracking-widest text-accent">
                  Opportunity {String(index + 1).padStart(2, '0')}
                </p>
                <span
                  className={`rounded-full px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wide ${
                    isGenericEvidence
                      ? 'border border-border-strong text-muted-strong'
                      : 'border border-success/40 bg-success/10 text-success'
                  }`}
                >
                  Evidence: {isGenericEvidence ? 'Weak' : 'Direct'}
                </span>
              </div>
              <h4 className="flex items-center gap-1.5 font-serif text-base font-semibold text-text">
                <IconTrendingUp className="h-3.5 w-3.5 shrink-0 text-accent" />
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
                <div className={`border-l-2 pl-3 ${isGenericEvidence ? 'border-border-strong' : 'border-success/40'}`}>
                  <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Evidence</dt>
                  <dd className="mt-1 font-serif text-sm italic leading-relaxed text-muted">"{item.evidence}"</dd>
                </div>
              </dl>
            </div>
          )
        })}
      </div>
    </div>
  )
}
