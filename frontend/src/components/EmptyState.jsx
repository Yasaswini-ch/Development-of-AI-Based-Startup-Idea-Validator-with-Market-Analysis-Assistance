import { IconGlobe } from './icons'

export default function EmptyState() {
  return (
    <div className="mt-6 flex flex-col items-center rounded-2xl border border-border bg-panel p-8 text-center shadow-sm">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-accent/10 text-accent">
        <IconGlobe className="h-5 w-5" />
      </span>
      <h2 className="mt-3 font-serif text-lg font-semibold text-text">No market data found yet</h2>
      <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-muted">
        Try adding more detail to your idea or problem statement and validate again.
      </p>
    </div>
  )
}
