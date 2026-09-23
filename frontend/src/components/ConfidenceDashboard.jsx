import useCountUp from '../hooks/useCountUp'
import ConfidenceGauge from './ConfidenceGauge'
import { IconGauge, IconAlertTriangle } from './icons'

// Three-tier read on any evidence-strength percentage, shared by every tile
// and the bar fill - low/mid/high map to the same danger/accent/success
// roles the rest of the app uses for "needs attention / okay / solid",
// instead of the old flat accent-or-muted binary that made every metric
// under 50% look identically unremarkable.
function tierFor(percent) {
  if (percent >= 67) return { text: 'text-success', bar: 'bg-success', tone: 'success' }
  if (percent >= 34) return { text: 'text-accent', bar: 'bg-accent', tone: 'accent' }
  return { text: 'text-danger', bar: 'bg-danger', tone: 'danger' }
}

// Metric tile shared by every stat in the dashboard. `percent` drives the
// count-up, the tier color, and a real progress bar - not just a number
// sitting on a flat gray card.
function MetricTile({ label, percent, detail }) {
  const value = useCountUp(Math.round(percent), 600)
  const tier = tierFor(percent)
  return (
    <div className="rounded-xl border border-border-strong bg-surface p-4">
      <p className={`font-serif text-2xl font-semibold ${tier.text}`}>{value}%</p>
      <p className="mt-1 font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-strong">{label}</p>
      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-border">
        <div className={`h-full rounded-full ${tier.bar}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
      </div>
      {detail && <p className="mt-2 text-xs leading-relaxed text-muted">{detail}</p>}
    </div>
  )
}

function recencyDetail(sourceRecency) {
  if (!sourceRecency || sourceRecency.sourcesWithKnownDate === 0) {
    return 'No dated sources available.'
  }
  const days = Math.round(sourceRecency.medianAgeDays)
  return `Median source age: ${days} day${days === 1 ? '' : 's'} (${sourceRecency.sourcesWithKnownDate}/${sourceRecency.totalSources} dated).`
}

// Replaces the old single "X% confidence" badge with a fuller picture of
// *why* that number is what it is - source coverage, cross-source
// agreement, direct-vs-inferred evidence, average relevance, and source
// recency (see docs/unique-features-plan.md §5.2 and
// backend/agent/graph.py's confidence_dashboard_node, which computes every
// field here without another LLM call).
export default function ConfidenceDashboard({ data }) {
  if (!data) return null

  const { sourceCoverage, crossSourceAgreement, directEvidenceRatio, averageRelevance, sourceRecency, label, percentage } = data
  const overall = typeof percentage === 'number' ? percentage : null
  const overallTier = tierFor(overall ?? 0)

  return (
    <div className="rounded-2xl border-2 border-accent/30 bg-panel p-6 shadow-sm sm:p-8">
      <div className="mb-5 flex items-center gap-2">
        <IconGauge className="h-4 w-4 text-accent" />
        <h3 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-text">
          Confidence dashboard
        </h3>
      </div>

      <div className="flex flex-col items-center gap-6 border-b border-border-strong pb-6 sm:flex-row sm:items-stretch">
        {overall !== null && (
          <div className="flex shrink-0 flex-col items-center gap-2 sm:border-r sm:border-border-strong sm:pr-6">
            <ConfidenceGauge percent={overall} size={128} label="Overall" tone={overallTier.tone} />
            {label && <p className="text-center font-mono text-[11px] font-semibold uppercase tracking-wide text-muted-strong">{label}</p>}
          </div>
        )}
        <p className="flex items-start gap-2 text-sm leading-relaxed text-muted sm:self-center">
          <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          This reflects evidence strength behind the analysis, not a guarantee the business will succeed. The
          breakdown below shows exactly what that number is built from.
        </p>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {sourceCoverage && (
          <MetricTile
            label="Source coverage"
            percent={sourceCoverage.percentage}
            detail={`${sourceCoverage.claimsWithSource}/${sourceCoverage.totalClaims} claims cite a source.`}
          />
        )}
        {crossSourceAgreement && (
          <MetricTile
            label="Cross-source agreement"
            percent={crossSourceAgreement.percentage}
            detail={`${crossSourceAgreement.claimsWithMultipleSources}/${crossSourceAgreement.totalClaims} claims cite 2+ sources.`}
          />
        )}
        {directEvidenceRatio && (
          <MetricTile
            label="Direct evidence"
            percent={directEvidenceRatio.percentage}
            detail={`${directEvidenceRatio.direct} direct vs ${directEvidenceRatio.inferred} inferred.`}
          />
        )}
        {typeof averageRelevance === 'number' && (
          <MetricTile
            label="Average relevance"
            percent={averageRelevance * 100}
            detail={recencyDetail(sourceRecency)}
          />
        )}
      </div>
    </div>
  )
}
