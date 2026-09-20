import useCountUp from '../hooks/useCountUp'
import { IconGauge, IconAlertTriangle } from './icons'

// Metric tile shared by every stat in the dashboard. `percent` drives the
// count-up + accent/muted tier the same way ValidationResults' old single
// confidence badge did, just repeated per-metric instead of once.
function MetricTile({ label, percent, detail }) {
  const value = useCountUp(Math.round(percent), 600)
  const tier = percent >= 50 ? 'text-accent' : 'text-muted'
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className={`font-serif text-2xl ${tier}`}>{value}%</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted">{label}</p>
      {detail && <p className="mt-1 text-xs leading-relaxed text-muted">{detail}</p>}
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

  const { sourceCoverage, crossSourceAgreement, directEvidenceRatio, averageRelevance, sourceRecency, label } = data

  return (
    <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconGauge className="h-4 w-4 text-accent" />
          Confidence dashboard
        </h3>
        {label && <span className="font-mono text-[11px] text-muted">{label}</span>}
      </div>

      <p className="mb-4 flex items-start gap-2 text-xs leading-relaxed text-muted">
        <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        This reflects evidence strength behind the analysis, not a guarantee the business will succeed.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
