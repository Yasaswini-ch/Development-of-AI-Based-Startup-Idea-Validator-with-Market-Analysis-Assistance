import { IconListChecks } from './icons'

// Pillar 5B: Stage-Gated MVP Delivery Roadmap (AFFINITY 5-pillar spec
// §4.5B). Renders mvp.deliveryRoadmap - a 3-phase timeline with exit-gate
// milestones and team sizing - computed deterministically by
// backend/agent/delivery_roadmap.py from this same node's own features.

function PhaseCard({ phase, index }) {
  return (
    <div className="rounded-xl border border-border-strong bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-serif text-sm font-semibold text-text">{phase.phaseName}</p>
        <span className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-muted">
          {phase.durationWeeks} wk{phase.durationWeeks === 1 ? '' : 's'}
        </span>
      </div>

      <div className="mt-3">
        <p className="font-mono text-[9px] uppercase tracking-widest text-muted">Deliverables</p>
        <ul className="mt-1.5 space-y-1">
          {phase.coreDeliverables.map((item, i) => (
            <li key={i} className="flex gap-2 text-xs leading-relaxed text-text">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3 border-t border-border pt-2.5">
        <p className="font-mono text-[9px] uppercase tracking-widest text-muted">Exit gate</p>
        <ul className="mt-1.5 space-y-1">
          {phase.exitGateMilestones.map((item, i) => (
            <li key={i} className="text-xs leading-relaxed text-accent">{item}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function MvpDeliveryRoadmap({ data }) {
  const phases = data?.phases || []
  if (phases.length === 0) return null

  return (
    <div className="mt-6 border-t border-border pt-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconListChecks className="h-3.5 w-3.5 text-accent" />
          Delivery Roadmap
        </h3>
        {data.totalTimelineWeeks && (
          <span className="font-mono text-[10px] uppercase tracking-wide text-muted">
            ~{data.totalTimelineWeeks} weeks total
          </span>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {phases.map((phase, i) => (
          <PhaseCard key={phase.phaseName} phase={phase} index={i} />
        ))}
      </div>

      {Array.isArray(data.teamComposition) && data.teamComposition.length > 0 && (
        <div className="mt-4 rounded-xl border border-border-strong bg-surface p-4">
          <p className="mb-2 font-mono text-[9px] uppercase tracking-widest text-muted">Team sizing</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {data.teamComposition.map((member) => (
              <div key={member.role} className="text-xs leading-relaxed">
                <span className="font-medium text-text">{member.role}</span>
                <span className="ml-1.5 font-mono text-[10px] text-accent">{member.allocation}</span>
                <p className="text-muted">{member.primaryFocus}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
