// What the product is actually built with. Every entry here is something the
// backend really calls (see backend/requirements.txt and agent/*.py) - keep it
// that way; a stack list that over-claims is worse than none.
const STACK = [
  {
    group: 'Reasoning',
    items: [
      ['LangGraph', 'Runs the pipeline as a graph, with the MVP and go-to-market branches in parallel.'],
      ['CrewAI', 'One focused agent per section, each with a single task and no free-roaming tools.'],
      ['LiteLLM', 'One interface over Groq and Gemini, with automatic fallback when a model is out of quota.'],
    ],
  },
  {
    group: 'Evidence',
    items: [
      ['Tavily + DuckDuckGo', 'Blended web search across five angles, deduplicated by URL.'],
      ['spaCy', 'Local entity recognition finds company names with no API call.'],
      ['Product Hunt, iTunes, Wikidata', 'Free public APIs that add ratings, pricing and descriptions to competitors.'],
    ],
  },
  {
    group: 'Delivery',
    items: [
      ['ReportLab', 'Builds the downloadable PDF report on the server.'],
      ['SendGrid', 'Emails the finished report through its HTTP API, which works on hosts that block SMTP.'],
      ['FastAPI', 'Serves the API and reports progress while a run is in flight.'],
    ],
  },
  {
    group: 'Accounts and storage',
    items: [
      ['PostgreSQL (Neon)', 'Keeps your reports and decision history, through SQLAlchemy.'],
      ['bcrypt + JWT', 'Password hashing and signed sessions.'],
      ['Google sign-in', 'Optional one-click sign-in, verified server-side.'],
    ],
  },
]

export default function TechStack() {
  return (
    <section className="mt-16" aria-labelledby="stack-heading">
      <p className="mb-2 text-center font-mono text-xs uppercase tracking-widest text-muted">What it is built with</p>
      <h2 id="stack-heading" className="mb-6 text-center font-serif text-2xl text-text">
        Real tools, each with one job.
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {STACK.map(({ group, items }) => (
          <div key={group} className="rounded-2xl border border-border bg-panel p-4 shadow-sm">
            <h3 className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-widest text-accent">{group}</h3>
            <ul className="space-y-2.5">
              {items.map(([name, role]) => (
                <li key={name} className="text-sm leading-relaxed text-muted">
                  <span className="font-semibold text-text">{name}</span> - {role}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}

export { STACK }
