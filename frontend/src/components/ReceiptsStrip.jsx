// Four things the report does that a plain chat answer does not, each stated as
// the mechanism rather than a statistic (no invented numbers), plus an honest
// limits line. All of it is implemented and can be seen in any report.
const RECEIPTS = [
  {
    title: 'Every citation is re-checked',
    body: 'A second pass reads each cited source and removes the citation when it does not support the claim. The report shows what was checked and what was removed.',
  },
  {
    title: 'Estimates say they are estimates',
    body: 'Market size, SAM, SOM and acquisition cost are labelled as sourced or estimated. Nothing that is a guess is dressed up as data.',
  },
  {
    title: 'Unknown stays unknown',
    body: 'If no source gave a competitor price, the table says "not found" instead of inventing one.',
  },
  {
    title: 'Failures are visible',
    body: 'If a step cannot run, that section says so. You never get a confident-looking answer built on a failed step.',
  },
]

export default function ReceiptsStrip() {
  return (
    <section className="mt-16" data-testid="receipts-strip">
      <p className="mb-2 text-center font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">The receipts</p>
      <h2 className="mb-6 text-center font-serif text-2xl font-semibold text-text sm:text-3xl">What we do that a chat reply will not.</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {RECEIPTS.map((r) => (
          <div key={r.title} className="rounded-2xl border border-border bg-panel p-5">
            <h3 className="font-serif text-base font-semibold text-text">{r.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">{r.body}</p>
          </div>
        ))}
      </div>
      <p className="mx-auto mt-4 max-w-2xl rounded-xl border border-dashed border-border-strong p-4 text-center text-xs leading-relaxed text-muted">
        <span className="font-semibold text-text">What it cannot do.</span> It reads public web pages, so private data and very new
        markets are thin. Competitor prices are often missing, sizing for niche markets is an estimate, and a verdict is a structured
        opinion to test with real customers, not a prediction.
      </p>
    </section>
  )
}
