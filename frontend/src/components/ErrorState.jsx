import { IconAlertTriangle } from './icons'

export default function ErrorState({ message, onRetry }) {
  return (
    <div className="mt-6 flex flex-col items-center rounded-2xl border border-danger/30 bg-panel p-8 text-center shadow-sm">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-danger/10 text-danger">
        <IconAlertTriangle className="h-5 w-5" />
      </span>
      <h2 className="mt-3 font-serif text-lg font-semibold text-text">Something went wrong</h2>
      <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-muted">
        {message || 'Something went wrong while fetching results. Please try again.'}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-full border border-border px-4 py-2 font-mono text-xs uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
        >
          Try again
        </button>
      )}
    </div>
  )
}
