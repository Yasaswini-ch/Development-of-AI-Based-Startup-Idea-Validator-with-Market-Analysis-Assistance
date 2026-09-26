import { IconFlag, IconListChecks } from './icons'
import ProvenanceBadge from './ProvenanceBadge'
import { roadmapWeekRanges } from '../lib/timeline'

// Pillar 5B: Stage-Gated MVP Delivery Roadmap (AFFINITY 5-pillar spec
// §4.5B). Renders mvp.deliveryRoadmap - a 3-phase timeline with exit-gate
// milestones and team sizing - computed deterministically by
// backend/agent/delivery_roadmap.py from the MVP agent's own features.
//
// This is the report's one build timeline (shown in the Roadmap tab); the
// GTM phases and the validation plan are labelled on the same week axis
// (lib/timeline.js). Durations, gates and team sizing come from fixed rules,
// so the block is labelled as an estimate.

function PhaseCard({ phase, range }) {
  return (
    <div className="rounded-xl border border-border-strong bg-surface p-4">
      <p className="font-mono text-[10.5px] uppercase tracking-widest text-muted">
        {range.label} · {phase.durationWeeks} wk{phase.durationWeeks === 1 ? '' : 's'}
      </p>
      <p className="mt-1 font-serif text-sm font-semibold text-text">{phase.phaseName}</p>

      <div className="mt-3">
        <p className="font-mono text-[10.5px] uppercase tracking-widest text-muted">Deliverables</p>
        <ul className="mt-1.5 space-y-1">
          {phase.coreDeliverables.map((item, i) => (
            <li key={i} className="flex gap-2 text-xs leading-relaxed text-text">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-border-strong" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3 border-t border-border pt-2.5">
        <p className="font-mono text-[10.5px] uppercase tracking-widest text-muted">Exit gate</p>
        <ul className="mt-1.5 space-y-1">
          {phase.exitGateMilestones.map((item, i) => (
            <li key={i} className="flex gap-2 text-xs leading-relaxed text-text">
              <IconFlag className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-strong" aria-hidden="true" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function MvpDeliveryRoadmap({ data }) {
  const phases = data?.phases || []
  if (phases.length === 0) return null
  const ranges = roadmapWeekRanges(data)

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconListChecks className="h-3.5 w-3.5 text-accent" />
          Delivery Roadmap
          <ProvenanceBadge
            status="inferred"
            label="Estimate"
            title="Durations, exit gates and team sizing come from rules of thumb applied to your MVP features, not from market data."
            className="ml-1"
          />
        </h3>
        {data.totalTimelineWeeks && (
          <span className="font-mono text-[10.5px] uppercase tracking-wide text-muted">
            ~{data.totalTimelineWeeks} weeks total
          </span>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {phases.map((phase, i) => (
          <PhaseCard key={phase.phaseName} phase={phase} range={ranges[i]} />
        ))}
      </div>

      {Array.isArray(data.teamComposition) && data.teamComposition.length > 0 && (
        <div className="mt-4 rounded-xl border border-border-strong bg-surface p-4">
          <p className="mb-2 font-mono text-[10.5px] uppercase tracking-widest text-muted">Suggested team</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {data.teamComposition.map((member) => (
              <div key={member.role} className="text-xs leading-relaxed">
                <span className="font-medium text-text">{member.role}</span>
                <span className="ml-1.5 font-mono text-[10.5px] text-muted-strong">{member.allocation}</span>
                <p className="text-muted">{member.primaryFocus}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
