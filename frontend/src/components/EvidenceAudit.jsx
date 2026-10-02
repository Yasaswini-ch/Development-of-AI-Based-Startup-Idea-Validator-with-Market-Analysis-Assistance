import { useState } from 'react'
import { IconCheckCircle, IconInfo } from './icons'

const SECTIONS = [
  ['marketOpportunity', 'Market'],
  ['swot', 'SWOT'],
  ['mvp', 'MVP'],
  ['gtm', 'Go-to-market'],
]

// Rolls up what the verification pass did to each section: how many cited
// claims it checked against their source text, and which lost their citation
// (the claim stays, relabelled inferred). Reports are older than this field or
// a section failed -> that section simply contributes nothing; if no section
// recorded an audit the card is not shown at all.
export function summarizeAudit(sections) {
  const rows = []
  for (const [key, label] of SECTIONS) {
    const v = sections?.[key]?.verification
    if (!v || typeof v !== 'object') continue
    rows.push({
      label,
      ran: v.ran === true,
      checked: Number.isFinite(v.checked) ? v.checked : 0,
      removed: Array.isArray(v.removed) ? v.removed : [],
    })
  }
  const ran = rows.filter((r) => r.ran)
  return {
    rows,
    sectionsChecked: ran.length,
    checked: ran.reduce((n, r) => n + r.checked, 0),
    removed: ran.reduce((n, r) => n + r.removed.length, 0),
  }
}

export default function EvidenceAudit({ marketOpportunity, swot, mvp, gtm }) {
  const [open, setOpen] = useState(false)
  const audit = summarizeAudit({ marketOpportunity, swot, mvp, gtm })
  if (audit.rows.length === 0) return null
  const notRun = audit.rows.length - audit.sectionsChecked
  const kept = audit.checked - audit.removed

  return (
    <div className="rounded-xl border border-border-strong bg-surface p-4" data-testid="evidence-audit">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <IconCheckCircle className="h-4 w-4 text-success" aria-hidden="true" />
          <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-strong">Evidence audit</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="font-mono text-[10px] uppercase tracking-wide text-accent hover:text-accent-hover"
        >
          {open ? 'Hide detail' : 'Show detail'}
        </button>
      </div>

      {audit.sectionsChecked > 0 ? (
        <p className="mt-2 text-sm leading-relaxed text-text">
          <span className="font-semibold">{audit.checked}</span> cited claims were checked against their source text:{' '}
          <span className="font-semibold text-success">{kept} held up</span>
          {audit.removed > 0 ? (
            <>
              , <span className="font-semibold text-warning">{audit.removed} lost their citation</span> because the source did not
              support them.
            </>
          ) : (
            '.'
          )}
        </p>
      ) : (
        <p className="mt-2 text-sm leading-relaxed text-muted">
          The source check did not run for this report, so citations are shown as the writing step gave them.
        </p>
      )}
      {notRun > 0 && audit.sectionsChecked > 0 && (
        <p className="mt-1 text-xs text-muted">The check did not run for {notRun} section{notRun === 1 ? '' : 's'}; those keep their original citations.</p>
      )}

      {open && (
        <ul className="mt-3 space-y-2 border-t border-border pt-3">
          {audit.rows.map((r) => (
            <li key={r.label} className="text-xs leading-relaxed text-muted">
              <span className="font-semibold text-text">{r.label}</span>
              {r.ran ? ` — ${r.checked} checked, ${r.removed.length} removed` : ' — check did not run'}
              {r.removed.map((c, i) => (
                <p key={i} className="mt-1 flex items-start gap-1.5 pl-3">
                  <IconInfo className="mt-0.5 h-3 w-3 shrink-0 text-warning" aria-hidden="true" />
                  <span>{c.text}</span>
                </p>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
