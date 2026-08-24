export default function ErrorState({ message, onRetry }) {
  return (
    <div className="mt-6 rounded-2xl border border-danger/40 bg-panel p-8 text-center">
      <p className="text-sm text-danger mb-3">
        {message || "Something went wrong while fetching results. Please try again."}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text transition-colors hover:border-accent"
        >
          Try again
        </button>
      )}
    </div>
  )
}
