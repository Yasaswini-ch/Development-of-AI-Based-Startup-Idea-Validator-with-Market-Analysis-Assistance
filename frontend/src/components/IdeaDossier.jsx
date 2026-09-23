// Displays a structured breakdown of the submitted idea back to the user
// so they can verify the AI interpreted it correctly before reading results.
// All logic is deterministic (no extra LLM call) — keywords are extracted
// from the idea text, confidence is derived from how much was filled in.

const STOP_WORDS = new Set([
  'a','an','the','and','or','but','in','on','at','to','for','of','with',
  'that','this','it','is','are','was','were','be','been','being','have',
  'has','had','do','does','did','will','would','could','should','may',
  'might','can','need','want','use','using','used','get','make','help',
  'our','my','your','their','its','we','i','you','they','he','she','who',
  'what','how','which','when','where','why','not','no','yes','so','if',
  'as','by','from','into','through','about','than','then','also','just',
  'very','more','most','some','any','all','each','other','new','app',
  'platform','solution','tool','service','product','based','system',
])

function extractKeywords(text, max = 7) {
  if (!text) return []
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 3 && !STOP_WORDS.has(w))
    .reduce((acc, w) => (acc.includes(w) ? acc : [...acc, w]), [])
    .slice(0, max)
}

function inputConfidence(idea, targetCustomer, problem) {
  const filled = [idea, targetCustomer, problem].filter((s) => s && s.trim().length > 10).length
  if (filled === 3) return { level: 'high', label: 'High confidence', note: 'All three fields provided — analysis is well-grounded.' }
  if (filled === 2) return { level: 'medium', label: 'Moderate confidence', note: 'One field was brief or missing — some sections may be broader than intended.' }
  return { level: 'low', label: 'Low confidence', note: 'Only the idea was provided — consider adding target customer and problem for sharper results.' }
}

const CONF_STYLES = {
  high:   'bg-success/10 text-success border-success/30',
  medium: 'bg-accent/10 text-accent border-accent/30',
  low:    'bg-danger/10 text-danger border-danger/30',
}

export default function IdeaDossier({ idea, targetCustomer, problem }) {
  if (!idea) return null

  const keywords = extractKeywords(idea)
  const conf = inputConfidence(idea, targetCustomer, problem)

  // Derive a short "concept title" — first sentence or first 60 chars
  const conceptTitle = (() => {
    const first = idea.split(/[.!?]/)[0].trim()
    return first.length > 70 ? first.slice(0, 67) + '…' : first
  })()

  return (
    <div className="rounded-2xl border border-border-strong bg-panel p-6 shadow-sm sm:p-8">
      {/* Header row */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-accent">§ Idea context</p>
          <h2 className="mt-1 font-serif text-xl font-semibold text-text">{conceptTitle}</h2>
        </div>
        <span className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-wide ${CONF_STYLES[conf.level]}`}>
          {conf.label}
        </span>
      </div>

      {conf.level === 'low' && (
        <div className="mb-5 flex gap-2.5 rounded-xl border border-danger/30 bg-danger/5 p-4 text-sm text-text">
          <span className="mt-0.5 text-danger">⚠</span>
          <p>{conf.note}</p>
        </div>
      )}

      {/* Three-column parameter grid */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Idea</p>
          <p className="text-sm leading-relaxed text-text">{idea}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Target customer</p>
          <p className="text-sm leading-relaxed text-text">{targetCustomer || <span className="text-muted italic">Not specified</span>}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Problem</p>
          <p className="text-sm leading-relaxed text-text">{problem || <span className="text-muted italic">Not specified</span>}</p>
        </div>
      </div>

      {/* Keywords */}
      {keywords.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">Research signals</p>
          <div className="flex flex-wrap gap-2">
            {keywords.map((kw) => (
              <span key={kw} className="rounded-full border border-border bg-surface px-3 py-1 font-mono text-[11px] text-muted-strong">
                #{kw}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
