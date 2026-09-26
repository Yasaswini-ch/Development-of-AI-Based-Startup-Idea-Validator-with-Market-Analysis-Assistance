import { IconFlask, IconListChecks, IconAlertTriangle, IconLightbulb, IconUsers, IconTrendingUp, IconNewspaper } from './icons'
import { ACTION_PLAN_WEEKS } from '../lib/timeline'

const ACTION_CATEGORIES = [
  { label: 'Build',    icon: IconLightbulb,  keys: ['build','ship','develop','create','implement','code','deploy','publish page','landing'], style: 'bg-accent/10 text-accent border-accent/30' },
  { label: 'Market',   icon: IconTrendingUp, keys: ['launch','product hunt','reddit','twitter','post','email','newsletter','content','article'], style: 'bg-info/10 text-info border-info/30' },
  { label: 'Research', icon: IconFlask,      keys: ['interview','survey','test','analyse','audit','measure','validate','feedback','nps'], style: 'bg-warning/10 text-warning border-warning/40' },
  { label: 'Outreach', icon: IconUsers,      keys: ['recruit','users','beta','partner','apply','reach','onboard'], style: 'bg-success/10 text-success border-success/30' },
  { label: 'Content',  icon: IconNewspaper,  keys: ['write','publish','content','piece','blog','seo','article','video'], style: 'bg-purple-100 text-purple-700 border-purple-300' },
]

function inferCategory(text = '') {
  const lower = text.toLowerCase()
  return ACTION_CATEGORIES.find((c) => c.keys.some((k) => lower.includes(k)))
    ?? { label: 'Task', icon: IconListChecks, style: 'bg-panel text-muted-strong border-border-strong' }
}

function ActionCard({ text, index }) {
  const cat = inferCategory(text)
  const Icon = cat.icon
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start gap-2.5">
        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[10.5px] font-bold ${cat.style}`}>
          {index + 1}
        </span>
        <p className="text-sm leading-relaxed text-text">{text}</p>
      </div>
      <div className="mt-3 flex items-center gap-1.5">
        <Icon className="h-3 w-3 text-muted" />
        <span className={`rounded-full border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${cat.style}`}>
          {cat.label}
        </span>
      </div>
    </div>
  )
}

function ExperimentCard({ item, index }) {
  if (typeof item === 'string') {
    return (
      <div className="rounded-xl border border-border bg-surface p-4">
        <div className="flex items-start gap-2.5">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 font-mono text-[10.5px] font-bold text-accent">
            {index + 1}
          </span>
          <p className="text-sm leading-relaxed text-text">{item}</p>
        </div>
        <div className="mt-3 flex items-center gap-1.5">
          <IconFlask className="h-3 w-3 text-muted" />
          <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-accent">Experiment</span>
        </div>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start gap-2.5">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 font-mono text-[10.5px] font-bold text-accent">
          {index + 1}
        </span>
        <h4 className="font-serif text-sm font-semibold leading-snug text-text">{item.hypothesis}</h4>
      </div>
      <dl className="mt-3 space-y-2">
        {item.method && (
          <div className="rounded-lg border border-border bg-panel p-2.5">
            <dt className="mb-0.5 font-mono text-[10.5px] uppercase tracking-widest text-muted">Method</dt>
            <dd className="text-sm leading-relaxed text-text">{item.method}</dd>
          </div>
        )}
        {item.successMetric && (
          <div className="rounded-lg border border-border bg-panel p-2.5">
            <dt className="mb-0.5 font-mono text-[10.5px] uppercase tracking-widest text-muted">Success metric</dt>
            <dd className="text-sm leading-relaxed text-text">{item.successMetric}</dd>
          </div>
        )}
      </dl>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {item.duration && (
          <span className="rounded-full border border-border bg-panel px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-muted">⏱ {item.duration}</span>
        )}
        {item.budget && item.budget !== 'unknown' && (
          <span className={`rounded-full border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${
            item.budget === 'low' ? 'border-success/30 bg-success/10 text-success'
            : item.budget === 'medium' ? 'border-warning/40 bg-warning/5 text-warning'
            : 'border-accent/30 bg-accent/10 text-accent'
          }`}>Budget: {item.budget}</span>
        )}
        <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-accent">Experiment</span>
      </div>
    </div>
  )
}

// Labels sit on the report's shared week axis (lib/timeline.js), matching
// the Delivery Roadmap above them in the Roadmap tab.
const COLUMNS = [
  {
    key: '7d',
    label: `Next 7 days · ${ACTION_PLAN_WEEKS['7d']}`,
    heading: 'Validate now',
    dot: 'bg-accent',
    header: 'border-accent/40 bg-accent/8',
    headingStyle: 'text-accent',
    countStyle: 'bg-accent text-white',
    border: 'border-accent/20',
  },
  {
    key: '30d',
    label: `Next 30 days · ${ACTION_PLAN_WEEKS['30d']}`,
    heading: 'Build traction',
    dot: 'bg-info',
    header: 'border-info/30 bg-info/8',
    headingStyle: 'text-info',
    countStyle: 'bg-info text-white',
    border: 'border-info/20',
  },
  {
    key: '90d',
    label: `Next 90 days · ${ACTION_PLAN_WEEKS['90d']}`,
    heading: 'Scale',
    dot: 'bg-success',
    header: 'border-success/30 bg-success/8',
    headingStyle: 'text-success',
    countStyle: 'bg-success text-white',
    border: 'border-success/20',
  },
]

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

export default function ExperimentsActionPlan({ experiments, actionPlan, error }) {
  const items = Array.isArray(experiments) ? experiments : []
  const plan = actionPlan && typeof actionPlan === 'object' && !Array.isArray(actionPlan) ? actionPlan : {}

  const mid = Math.ceil(items.length / 2)
  const expByPhase = { '7d': items.slice(0, mid), '30d': items.slice(mid), '90d': [] }

  function planItems(key) {
    const map = { '7d': plan.next7Days, '30d': plan.next30Days, '90d': plan.next90Days }
    const p = map[key]
    if (!p) return []
    if (Array.isArray(p)) return p
    if (Array.isArray(p.items)) return p.items
    return []
  }
  function planTitle(key) {
    const map = { '7d': plan.next7Days, '30d': plan.next30Days, '90d': plan.next90Days }
    const p = map[key]
    return p && typeof p === 'object' && !Array.isArray(p) ? p.title : null
  }

  const hasPlan = plan.next7Days || plan.next30Days || plan.next90Days
  if (items.length === 0 && !hasPlan) return <Unavailable error={error} />

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {COLUMNS.map((col) => {
        const exps = expByPhase[col.key] ?? []
        const pItems = planItems(col.key)
        const title = planTitle(col.key)
        const totalCards = exps.length + pItems.length
        if (totalCards === 0 && !title) return null

        return (
          <div key={col.key} className={`flex flex-col rounded-2xl border ${col.border} bg-panel overflow-hidden`}>
            {/* Column header */}
            <div className={`border-b px-4 py-3 ${col.header}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${col.dot}`} />
                  <span className={`font-mono text-[10px] font-semibold uppercase tracking-widest ${col.headingStyle}`}>
                    {col.heading}
                  </span>
                </div>
                <span className={`rounded-full px-1.5 py-0.5 font-mono text-[10.5px] font-bold ${col.countStyle}`}>
                  {totalCards}
                </span>
              </div>
              <p className="mt-0.5 pl-4 font-mono text-[10.5px] text-muted">{col.label}</p>
            </div>

            {/* Cards */}
            <div className="flex flex-col gap-3 p-3">
              {exps.map((exp, i) => <ExperimentCard key={`e-${i}`} item={exp} index={i} />)}

              {pItems.length > 0 && (
                <>
                  {exps.length > 0 && (
                    <div className="flex items-center gap-2 py-1">
                      <div className="h-px flex-1 bg-border" />
                      <span className="font-mono text-[10.5px] uppercase tracking-widest text-muted">
                        {title || 'Action items'}
                      </span>
                      <div className="h-px flex-1 bg-border" />
                    </div>
                  )}
                  {exps.length === 0 && title && (
                    <p className="font-mono text-[10.5px] uppercase tracking-widest text-muted">{title}</p>
                  )}
                  {pItems.map((entry, i) => (
                    <ActionCard key={`a-${i}`} text={typeof entry === 'string' ? entry : entry.text} index={i} />
                  ))}
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
