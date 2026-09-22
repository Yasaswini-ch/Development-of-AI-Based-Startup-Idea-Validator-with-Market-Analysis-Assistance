import { useEffect, useState } from 'react'
import { IconLink, IconX } from './icons'
import { getHistory, removeHistoryEntry, clearHistory } from '../lib/history'
import { authHeaders } from '../lib/auth'

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function CopyLinkButton({ sessionId }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    const link = `${window.location.origin}${window.location.pathname}?session=${sessionId}`
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API unavailable - the session id is still visible in the
      // row itself, just not auto-copied.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
    >
      <IconLink className="h-3 w-3" />
      {copied ? 'Copied!' : 'Copy link'}
    </button>
  )
}

// onOpen is optional - when the host page (App.jsx) can resume a session
// in place, pass a callback; otherwise this still works as a read-only,
// copy-the-link list.
//
// With a `token` (signed in), this lists GET /me/history - the account's
// own board, server-side. Without one, it falls back to the device-local
// list (lib/history.js) exactly as before accounts existed. The server
// list has no per-entry delete yet (no DELETE /me/history/{id} endpoint) -
// "Remove"/"Clear" only apply to the local list, since a signed-in board is
// meant to be the durable record, not something to prune from this screen.
export default function HistoryPanel({ apiUrl, token, onOpen, onBack }) {
  const [entries, setEntries] = useState(token ? [] : getHistory)
  const [isLoading, setIsLoading] = useState(Boolean(token))
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    if (!token) return
    let cancelled = false
    setIsLoading(true)
    setLoadError('')
    fetch(`${apiUrl}/me/history`, { headers: authHeaders(token) })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        if (!cancelled) setEntries(data.entries || [])
      })
      .catch(() => {
        if (!cancelled) setLoadError('Could not load your account history. Please try again.')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [apiUrl, token])

  function handleRemove(sessionId) {
    removeHistoryEntry(sessionId)
    setEntries(getHistory())
  }

  function handleClear() {
    clearHistory()
    setEntries([])
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-accent">History</p>
          <h2 className="font-serif text-2xl text-text">Your past validations</h2>
        </div>
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="rounded-full border border-border bg-surface px-4 py-2 font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
          >
            Back
          </button>
        )}
      </div>

      <p className="mb-4 text-sm leading-relaxed text-muted">
        {token
          ? "Saved to your account - these validations follow you across devices as long as you're signed in with this email."
          : 'Saved on this device only - there\'s no account system, so switching browsers or clearing site data loses this list. Use "Copy link" to save a session somewhere durable (your email, notes) before that happens. The same links also work as input for Compare.'}
      </p>

      {isLoading ? (
        <div className="rounded-2xl border border-border bg-panel p-8 text-center font-mono text-xs uppercase tracking-widest text-muted cursor-blink">
          Loading your history
        </div>
      ) : loadError ? (
        <div className="rounded-2xl border border-danger/30 bg-panel p-8 text-center text-sm text-danger">{loadError}</div>
      ) : entries.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-panel p-8 text-center text-sm text-muted">
          {token ? 'No validations yet on this account. Run one and it\'ll show up here.' : 'No validations yet on this device. Run one and it\'ll show up here.'}
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <div
              key={entry.sessionId}
              className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-panel p-4 shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-serif text-base text-text">{entry.idea || 'Untitled idea'}</p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wide text-muted/70">
                  {entry.targetCustomer ? `${entry.targetCustomer} · ` : ''}
                  {formatDate(entry.createdAt)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {onOpen && (
                  <button
                    type="button"
                    onClick={() => onOpen(entry.sessionId)}
                    className="rounded-full border border-border bg-surface px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
                  >
                    Open
                  </button>
                )}
                <CopyLinkButton sessionId={entry.sessionId} />
                {!token && (
                  <button
                    type="button"
                    onClick={() => handleRemove(entry.sessionId)}
                    aria-label="Remove from history"
                    className="shrink-0 rounded-full p-1.5 text-muted transition-colors hover:bg-surface hover:text-danger"
                  >
                    <IconX className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!token && entries.length > 0 && (
        <button
          type="button"
          onClick={handleClear}
          className="mt-4 font-mono text-[11px] uppercase tracking-wide text-muted hover:text-danger"
        >
          Clear history
        </button>
      )}
    </div>
  )
}
