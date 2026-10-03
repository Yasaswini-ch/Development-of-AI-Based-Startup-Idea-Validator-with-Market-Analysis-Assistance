import { useState } from 'react'

// A small, clickable mock of the report so visitors see its shape before they
// run anything. Everything here is sample text for an invented idea - the
// frame says so - and mirrors the real tab names in ValidationResults.jsx.
const TABS = [
  {
    key: 'evidence',
    label: 'Evidence',
    heading: '18 sources across 5 research angles',
    lines: [
      'Industry report: support analytics spend growing year on year',
      'Forum thread: teams still copy call notes into spreadsheets by hand',
      'Pricing page: incumbent charges per seat, with a minimum contract',
    ],
  },
  {
    key: 'market',
    label: 'Market',
    heading: 'Growing market, size only partly sourced',
    lines: [
      'Market signal: 4 of 5 sources describe growth',
      'Viability: demand urgency strong, capital efficiency moderate',
      'TAM comes from a source; SAM and SOM are sourced or a badged estimate',
    ],
  },
  {
    key: 'competitors',
    label: 'Competitors',
    heading: '6 rivals found, 2 direct and 4 indirect',
    lines: [
      'Direct: tools that already turn calls into summaries',
      'Indirect: general survey and ticketing platforms',
      'A comparison table sets each against your idea',
    ],
  },
  {
    key: 'customers',
    label: 'Customers',
    heading: '3 customer segments',
    lines: [
      'Support leads at mid-size SaaS: want fewer manual reports',
      'Product managers: want call themes without listening in',
      'Verbatim quotes from the sources back each pain point',
    ],
  },
  {
    key: 'gaps',
    label: 'Gaps',
    heading: '4 openings where pain meets weak coverage',
    lines: [
      'Weekly digest format that rivals do not offer',
      'Small teams priced out by seat minimums',
      'An entry wedge is suggested for the first customers',
    ],
  },
  {
    key: 'risks',
    label: 'Risks',
    heading: 'Strengths, bear case and assumptions',
    lines: [
      'Bear case: incumbents could add a digest feature quickly',
      'Riskiest assumption: buyers will pay for a weekly summary',
      'Each claim is tagged Grounded or Inferred',
    ],
  },
  {
    key: 'build',
    label: 'Build & Ship',
    heading: 'MVP, revenue models and go-to-market',
    lines: [
      'Build first: call import and a one-page digest',
      'Revenue: flat team plan before per-seat pricing',
      'First customers: support communities and outbound to leads',
    ],
  },
  {
    key: 'roadmap',
    label: 'Roadmap',
    heading: 'Experiments and a 7, 30 and 90 day plan',
    lines: [
      'Week 1: ten problem interviews with support leads',
      'Day 30: pilot the digest with three teams',
      'Day 90: decide on pricing from pilot results',
    ],
  },
]

const STATS = [
  ['18', 'sources'],
  ['6', 'competitors'],
  ['4', 'gaps'],
  ['3', 'segments'],
]

export default function SampleReportPreview() {
  const [active, setActive] = useState(0)
  const tab = TABS[active]

  function handleKeyDown(e) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = (active + (e.key === 'ArrowRight' ? 1 : -1) + TABS.length) % TABS.length
    setActive(next)
    document.getElementById(`sample-tab-${next}`)?.focus()
  }

  return (
    <section
      className="fade-in-up mx-auto mt-10 max-w-3xl"
      style={{ animationDelay: '250ms' }}
      aria-labelledby="sample-report-heading"
    >
      <p className="mb-2 text-center font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">What you get</p>
      <h2 id="sample-report-heading" className="mb-6 text-center font-serif text-2xl font-semibold text-text sm:text-3xl">
        A full report in eight tabs.
      </h2>
      <div className="overflow-hidden rounded-2xl border border-border-strong bg-panel shadow-sm">
        <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Validation report</span>
          <span className="rounded-full border border-border-strong px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted">
            Sample
          </span>
        </div>

        <div className="grid grid-cols-4 divide-x divide-border border-b border-border">
          {STATS.map(([value, label]) => (
            <div key={label} className="px-2 py-3 text-center">
              <p className="font-serif text-xl font-semibold text-text">{value}</p>
              <p className="font-mono text-[10px] uppercase tracking-wide text-muted">{label}</p>
            </div>
          ))}
        </div>

        <div
          role="tablist"
          aria-label="Sample report sections"
          onKeyDown={handleKeyDown}
          className="flex gap-1 overflow-x-auto border-b border-border px-3 pt-2"
        >
          {TABS.map((t, i) => (
            <button
              key={t.key}
              id={`sample-tab-${i}`}
              role="tab"
              type="button"
              aria-selected={active === i}
              aria-controls="sample-tab-panel"
              tabIndex={active === i ? 0 : -1}
              onClick={() => setActive(i)}
              className={`shrink-0 border-b-2 px-3 py-2 font-mono text-[11px] uppercase tracking-wide transition-colors ${
                active === i ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-text'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div
          id="sample-tab-panel"
          role="tabpanel"
          aria-labelledby={`sample-tab-${active}`}
          className="min-h-[11rem] p-5 text-left"
        >
          <h3 className="font-serif text-lg text-text">{tab.heading}</h3>
          <ul className="mt-3 space-y-2">
            {tab.lines.map((line) => (
              <li key={line} className="flex gap-2.5 text-sm leading-relaxed text-muted-strong">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {line}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-2 text-center font-mono text-[10px] uppercase tracking-wide text-muted">
        Illustrative content for an invented idea. Your report is built from your own research.
      </p>
    </section>
  )
}

export { TABS }
