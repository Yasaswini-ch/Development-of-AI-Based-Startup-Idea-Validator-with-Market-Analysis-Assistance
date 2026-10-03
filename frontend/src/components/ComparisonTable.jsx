// How Affinity differs from asking a general chatbot (ChatGPT, Claude and the
// like). Kept to differences that are true of this codebase; chatbots can
// browse and reason well, so the claim is about structure and checkability,
// not that they are bad.
const ROWS = [
  ['Evidence', 'Searches the web in five fixed angles and lists every source it used', 'Answers from training data unless you ask it to search; sources vary by prompt'],
  ['Claims', 'Each claim is tagged Grounded (cites a source) or Inferred, and a verifier checks the citation', 'Claims read the same whether or not anything backs them'],
  ['Scoring', 'Opportunity score, viability index and verdict come from plain code, so the same evidence gives the same numbers', 'A score, if given, is whatever the model says that time'],
  ['Competitors', 'Found in the sources, labelled direct or indirect, compared with your idea in a table', 'A list from memory, which can include dead or invented products'],
  ['Output', 'A structured report in tabs, a PDF, and an emailed copy', 'A chat reply you copy out yourself'],
  ['Follow-ups', 'The advisor answers from your report and jumps to the section it used', 'Answers from the conversation; no report to point at'],
  ['History', 'Saves runs and shows how the verdict changed when you changed the idea', 'Each chat starts over unless you carry the context yourself'],
]

export default function ComparisonTable() {
  return (
    <section className="mt-16" aria-labelledby="compare-heading">
      <p className="mb-2 text-center font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">Why not just ask a chatbot?</p>
      <h2 id="compare-heading" className="mb-3 text-center font-serif text-2xl font-semibold text-text sm:text-3xl">
        A chatbot answers. Affinity shows its work.
      </h2>
      <p className="mx-auto mb-6 max-w-2xl text-center text-sm leading-relaxed text-muted">
        General assistants such as ChatGPT and Claude are strong at reasoning, and you can still use them alongside this.
        What differs is how checkable the answer is.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-border bg-panel shadow-sm">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="border-b border-border-strong font-mono text-[11px] uppercase tracking-widest text-muted">
              <th scope="col" className="px-4 py-3">
                <span className="sr-only">Aspect</span>
              </th>
              <th scope="col" className="px-4 py-3 text-accent">Affinity</th>
              <th scope="col" className="px-4 py-3">A general chatbot</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(([label, ours, theirs]) => (
              <tr key={label} className="border-b border-border align-top last:border-0">
                <th scope="row" className="px-4 py-3 font-semibold text-text">{label}</th>
                <td className="px-4 py-3 leading-relaxed text-text">{ours}</td>
                <td className="px-4 py-3 leading-relaxed text-muted">{theirs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export { ROWS }
