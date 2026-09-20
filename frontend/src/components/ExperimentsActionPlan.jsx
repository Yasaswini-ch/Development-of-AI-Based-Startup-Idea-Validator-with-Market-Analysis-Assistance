import { IconFlask, IconListChecks, IconAlertTriangle } from './icons'

const BUDGET_STYLES = {
  low: 'border-border bg-panel text-muted',
  medium: 'border-amber-300 bg-amber-50 text-amber-700',
  high: 'border-accent/30 bg-accent/5 text-accent',
  unknown: 'border-border bg-panel text-muted',
}

function BudgetBadge({ budget }) {
  const level = BUDGET_STYLES[budget] ? budget : 'unknown'
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${BUDGET_STYLES[level]}`}>
      Budget: {level}
    </span>
  )
}

function ExperimentCard({ item }) {
  const relatedRiskIds = Array.isArray(item.relatedRiskIds) ? item.relatedRiskIds : []
  return (
    <article className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-start gap-2">
        <IconFlask className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <h4 className="text-sm font-semibold leading-snug text-text">{item.hypothesis}</h4>
      </div>
      <dl className="mt-3 space-y-2">
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Method</dt>
          <dd className="mt-1 text-sm leading-relaxed text-text">{item.method}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-widest text-muted">Success metric</dt>
          <dd className="mt-1 text-sm leading-relaxed text-text">{item.successMetric}</dd>
        </div>
      </dl>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {item.duration && (
          <span className="rounded-full border border-border bg-panel px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted">
            {item.duration}
          </span>
        )}
        <BudgetBadge budget={item.budget} />
        {relatedRiskIds.map((riskId) => (
          <span
            key={riskId}
            className="rounded-full border border-danger/30 bg-danger/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-danger"
          >
            {riskId}
          </span>
        ))}
      </div>
    </article>
  )
}

function PlanColumn({ title, heading, items }) {
  const list = Array.isArray(items) ? items : []
  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h4 className="font-mono text-[11px] uppercase tracking-widest text-accent">{title}</h4>
      {heading && <p className="mt-1 text-sm font-medium text-text">{heading}</p>}
      {list.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {list.map((entry, index) => (
            <li key={index} className="flex gap-2 text-sm leading-relaxed text-text">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
              <span>{typeof entry === 'string' ? entry : entry.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted">No action items yet.</p>
      )}
    </div>
  )
}

function Unavailable({ error }) {
  return (
    <div className="flex flex-col items-center justify-center p-2 text-center">
      <IconAlertTriangle className="h-5 w-5 text-muted" />
      <p className="mt-2 text-sm font-medium text-text">Experiments and action plan aren&apos;t available yet</p>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
        {error || 'This section is generated once the validation experiment and action plan agents complete.'}
      </p>
    </div>
  )
}

// Renders Tracks C/D (docs/unique-features-plan.md §5.4-5.5): validation
// experiments converting risky assumptions into testable hypotheses, and
// the 7/30/90-day founder action plan. Neither has a backend agent yet
// (agent/experiment_generator.py, agent/action_plan.py), so `experiments`
// and `actionPlan` are undefined from the live API today - this renders
// the same "not available" state that covers a genuinely failed section,
// and should be replaced with data once those land (see mocks/validationMock.js).
export default function ExperimentsActionPlan({ experiments, actionPlan, error }) {
  const items = Array.isArray(experiments) ? experiments : []
  const plan = actionPlan || {}
  const hasPlan = plan.next7Days || plan.next30Days || plan.next90Days

  if (items.length === 0 && !hasPlan) {
    return <Unavailable error={error} />
  }

  return (
    <div className="space-y-8">
      {items.length > 0 && (
        <section>
          <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconFlask className="h-3.5 w-3.5 text-accent" />
            Validation experiments
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {items.map((item, index) => (
              <ExperimentCard key={index} item={item} />
            ))}
          </div>
        </section>
      )}

      {hasPlan && (
        <section>
          <h3 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-muted">
            <IconListChecks className="h-3.5 w-3.5 text-accent" />
            Founder action plan
          </h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <PlanColumn title="Next 7 days" heading={plan.next7Days?.title} items={plan.next7Days?.items} />
            <PlanColumn title="Next 30 days" heading={plan.next30Days?.title} items={plan.next30Days?.items} />
            <PlanColumn title="Next 90 days" heading={plan.next90Days?.title} items={plan.next90Days?.items} />
          </div>
        </section>
      )}
    </div>
  )
}
