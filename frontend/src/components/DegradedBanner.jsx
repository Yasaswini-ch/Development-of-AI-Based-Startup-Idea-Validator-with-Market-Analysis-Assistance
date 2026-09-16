import { IconInfo } from './icons'

// Shown above a section's content whenever the backend used its
// deterministic, evidence-based fallback instead of a real AI-reasoned
// result (see backend/agent/deterministic_fallback.py) - the data is real
// and grounded in the actual sources gathered for this idea, just not as
// deep as a full LLM analysis, so this is a distinct, honest state from
// both a full result and an outright failure ("...wasn't available").
export default function DegradedBanner() {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-accent/30 bg-accent/5 px-3 py-2">
      <IconInfo className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
      <p className="text-xs leading-relaxed text-muted">
        Showing an automated, evidence-based summary - full AI reasoning is
        temporarily unavailable for this section.
      </p>
    </div>
  )
}
