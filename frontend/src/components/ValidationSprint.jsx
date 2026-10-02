import { useState } from 'react'

// Simple stable key so ticks survive a reload of the same report.
function keyFor(sprint) {
  const text = JSON.stringify(sprint?.weeks?.[0]?.tasks?.[0] ?? '')
  let h = 0
  for (let i = 0; i < text.length; i += 1) h = (h * 31 + text.charCodeAt(i)) | 0
  return `affinity:sprint:${h}`
}

function readTicks(key) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeTicks(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // storage unavailable: the checklist still works for this visit
  }
}

function scriptText(script) {
  const lines = ['Interview script', '']
  if (script.audience) lines.push(`Talk to: ${script.audience}`, '')
  lines.push('Ground rules:', ...script.rules.map((r) => `- ${r}`), '', 'Opening:', ...script.opening.map((q) => `- ${q}`), '')
  lines.push('Probes:')
  script.probes.forEach((p) => lines.push(`- ${p.ask}`, `    Listen for: ${p.listenFor}`, `    Red flag: ${p.redFlag}`))
  lines.push('', 'Closing:', ...script.closing.map((q) => `- ${q}`))
  return lines.join('\n')
}

function Sprint({ sprint }) {
  const storeKey = keyFor(sprint)
  const [ticks, setTicks] = useState(() => readTicks(storeKey))
  const toggle = (id) => {
    const next = { ...ticks, [id]: !ticks[id] }
    setTicks(next)
    writeTicks(storeKey, next)
  }
  const all = sprint.weeks.flatMap((w) => w.tasks.map((_, i) => `${w.week}-${i}`))
  const done = all.filter((id) => ticks[id]).length
  return (
    <div className="rounded-2xl border border-border-strong bg-surface p-5" data-testid="validation-sprint">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-text">4-week validation sprint</h3>
        <span className="font-mono text-[10px] text-muted" data-testid="sprint-progress">
          {done} of {all.length} done
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">{sprint.note}</p>
      <div className="mt-4 space-y-4">
        {sprint.weeks.map((w) => (
          <div key={w.week}>
            <p className="font-mono text-[10px] uppercase tracking-widest text-accent">
              Week {w.week} · {w.title}
            </p>
            <ul className="mt-2 space-y-2">
              {w.tasks.map((t, i) => {
                const id = `${w.week}-${i}`
                return (
                  <li key={id} className="rounded-lg border border-border bg-panel p-3">
                    <label className="flex items-start gap-2 text-sm leading-relaxed text-text">
                      <input type="checkbox" className="mt-1" checked={!!ticks[id]} onChange={() => toggle(id)} aria-label={t.task} />
                      <span className={ticks[id] ? 'text-muted line-through' : ''}>{t.task}</span>
                    </label>
                    <p className="mt-1.5 pl-6 text-xs text-success">Pass: {t.confirmsIf}</p>
                    <p className="pl-6 text-xs text-danger">Fail: {t.killsIf}</p>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}

function Script({ script }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(scriptText(script))
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="rounded-2xl border border-border-strong bg-surface p-5" data-testid="interview-script">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-text">Customer interview script</h3>
        <button type="button" onClick={copy} className="font-mono text-[10px] uppercase tracking-wide text-accent hover:text-accent-hover">
          {copied ? 'Copied' : 'Copy script'}
        </button>
      </div>
      {script.audience && <p className="mt-1 text-xs text-muted">Talk to: {script.audience}</p>}
      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-relaxed text-muted-strong">
        {script.rules.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
      <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-muted">Opening</p>
      <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm text-text">
        {script.opening.map((q, i) => (
          <li key={i}>{q}</li>
        ))}
      </ol>
      <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-muted">Probes, one per risky assumption</p>
      <div className="mt-1 space-y-2">
        {script.probes.map((p, i) => (
          <div key={i} className="rounded-lg border border-border bg-panel p-3">
            <p className="text-xs text-muted">Tests: {p.assumption}</p>
            <p className="mt-1 text-sm font-medium text-text">{p.ask}</p>
            <p className="mt-1 text-xs text-success">Listen for: {p.listenFor}</p>
            <p className="text-xs text-danger">Red flag: {p.redFlag}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-muted">Closing</p>
      <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm text-text">
        {script.closing.map((q, i) => (
          <li key={i}>{q}</li>
        ))}
      </ol>
    </div>
  )
}

export default function ValidationSprint({ plan }) {
  const sprint = plan?.sprint?.weeks?.length ? plan.sprint : null
  const script = plan?.interviewScript?.probes?.length ? plan.interviewScript : null
  if (!sprint && !script) return null
  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-2">
      {sprint && <Sprint sprint={sprint} />}
      {script && <Script script={script} />}
    </div>
  )
}
