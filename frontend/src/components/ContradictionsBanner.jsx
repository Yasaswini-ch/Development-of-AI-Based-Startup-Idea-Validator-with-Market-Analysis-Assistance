import { IconAlertTriangle } from './icons'
import Citation from './Citation'

// Renders the flags backend/agent/contradiction_detector.py surfaces
// (Track B, docs/unique-features-plan.md §5.3): deterministic tensions
// across already-computed artifacts, e.g. a growing market alongside a
// price-resistant segment. Each flag cites the sourceIds of the claims it
// was built from - same Citation UI as every other claim in the app - so
// it can be verified the same way, not taken as an unexplained warning.
export default function ContradictionsBanner({ data, sourceMap }) {
  const contradictions = Array.isArray(data) ? data : []
  if (contradictions.length === 0) return null

  return (
    <section className="rounded-2xl border border-amber-300 bg-amber-50 p-6 shadow-sm sm:p-8">
      <h3 className="mb-1 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-amber-700">
        <IconAlertTriangle className="h-4 w-4" />
        Contradictions worth a second look
      </h3>
      <p className="mb-4 text-xs leading-relaxed text-amber-700/80">
        These are heuristic tensions between different sections of the analysis, not proof either side is wrong.
      </p>
      <ul className="space-y-2">
        {contradictions.map((item, index) => (
          <li key={item.type || index} className="rounded-xl border border-amber-200 bg-white/60 p-3 text-sm leading-relaxed text-text">
            {item.summary}
            {sourceMap && <Citation sourceIds={item.sourceIds} sourceMap={sourceMap} />}
          </li>
        ))}
      </ul>
    </section>
  )
}
