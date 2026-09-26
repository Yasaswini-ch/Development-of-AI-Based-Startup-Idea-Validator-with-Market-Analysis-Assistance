import { IconAlertTriangle, IconTrendingUp } from './icons'
import StrategicWedgeSection from './StrategicWedgeCard'

const _GENERIC_EVIDENCE = 'Grounded in the retrieved market sources.'

const TIER = [
  { label: 'High opportunity', style: 'bg-success/10 text-success border-success/40', bar: 'bg-success', width: 'w-full' },
  { label: 'Mid opportunity',  style: 'bg-accent/10 text-accent border-accent/30',   bar: 'bg-accent',  width: 'w-2/3'  },
  { label: 'Watch',            style: 'bg-border text-muted-strong border-border',    bar: 'bg-border',  width: 'w-1/3'  },
]

function tierFor(index, total) {
  if (index === 0) return TIER[0]
  if (index < Math.ceil(total / 2)) return TIER[1]
  return TIER[2]
}

function EmptyWhiteSpace() {
  return (
    <div className="flex flex-col items-center justify-center p-6 text-center">
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
  if (opportunities.length === 0) return <EmptyWhiteSpace />

  return (
    <div>
      {data.summary && (
        <p className="mb-5 text-sm leading-relaxed text-text">{data.summary}</p>
      )}
      {data.competitionNote && (
        <p className="mb-5 rounded-xl border border-border bg-surface p-3 text-sm leading-relaxed text-muted">
          {data.competitionNote}
        </p>
      )}

      <div className="space-y-4">
        {opportunities.map((item, index) => {
          const isGenericEvidence = !item.evidence || item.evidence === _GENERIC_EVIDENCE
          const tier = tierFor(index, opportunities.length)

          return (
            <div key={index} className="rounded-2xl border border-border-strong bg-surface overflow-hidden">
              {/* Top bar — opportunity number + tier */}
              <div className="flex items-center justify-between border-b border-border px-5 py-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/10 font-mono text-xs font-bold text-accent">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <h4 className="flex items-center gap-1.5 font-serif text-base font-semibold text-text">
                    <IconTrendingUp className="h-3.5 w-3.5 shrink-0 text-accent" />
                    {item.title}
                  </h4>
                </div>
                <span className={`shrink-0 rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase tracking-wide ${tier.style}`}>
                  {tier.label}
                </span>
              </div>

              {/* Opportunity bar */}
              <div className="h-1 w-full bg-border">
                <div className={`h-1 ${tier.bar} ${tier.width} transition-all`} />
              </div>

              {/* Body */}
              <div className="grid gap-0 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border">
                <div className="p-5">
                  <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Customer pain</p>
                  <p className="text-sm leading-relaxed text-text">{item.why}</p>
                </div>
                <div className="p-5">
                  <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Startup fit</p>
                  <p className="text-sm leading-relaxed text-text">{item.fit}</p>
                </div>
                <div className="p-5">
                  <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Evidence</p>
                  {isGenericEvidence ? (
                    <p className="text-sm italic leading-relaxed text-muted">Grounded in market sources.</p>
                  ) : (
                    <p className={`border-l-2 pl-3 font-serif text-sm italic leading-relaxed text-muted ${isGenericEvidence ? 'border-border' : 'border-success/50'}`}>
                      "{item.evidence}"
                    </p>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <StrategicWedgeSection blueprints={data.blueprints} />
    </div>
  )
}
