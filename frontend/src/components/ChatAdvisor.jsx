import { useEffect, useRef, useState } from 'react'
import { IconAlertTriangle, IconLightbulb, IconMessageCircle, IconX } from './icons'

const MAX_MESSAGES = 40

export default function ChatAdvisor({ sessionId, apiUrl }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  // Tracks advisor replies the user hasn't seen yet while the bubble is
  // collapsed, so reopening it doesn't lose the "something happened" signal
  // a fully hidden panel would otherwise give up.
  const [unreadCount, setUnreadCount] = useState(0)
  const transcriptRef = useRef(null)
  const submissionLock = useRef(false)

  useEffect(() => {
    if (!isOpen) return
    const transcript = transcriptRef.current
    if (transcript) transcript.scrollTop = transcript.scrollHeight
  }, [isOpen, messages, isSubmitting, error])

  function openPanel() {
    setIsOpen(true)
    setUnreadCount(0)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const message = input.trim()
    if (!message || submissionLock.current) return

    submissionLock.current = true
    setIsSubmitting(true)
    setError('')
    setInput('')
    setMessages((current) => [...current, { role: 'user', text: message }].slice(-MAX_MESSAGES))

    try {
      const response = await fetch(`${apiUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, message }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'The advisor could not answer right now.')
      if (typeof data.reply !== 'string') throw new Error('The advisor returned an invalid response.')

      setMessages((current) => [...current, { role: 'advisor', text: data.reply }].slice(-MAX_MESSAGES))
      if (!isOpen) setUnreadCount((count) => count + 1)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Could not reach the advisor. Please try again.',
      )
    } finally {
      submissionLock.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3 sm:bottom-6 sm:right-6">
      {isOpen && (
        <section className="flex w-[calc(100vw-2.5rem)] max-w-sm flex-col overflow-hidden rounded-2xl border border-border bg-panel shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="flex items-center gap-2 font-serif text-lg text-text">
              <IconLightbulb className="h-5 w-5 text-accent" />
              Validation advisor
            </h2>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
              className="rounded-full p-1 text-muted transition-colors hover:bg-surface hover:text-text"
            >
              <IconX className="h-4 w-4" />
            </button>
          </div>

          <div
            ref={transcriptRef}
            className="max-h-80 min-h-48 space-y-3 overflow-y-auto px-5 py-4"
            aria-live="polite"
          >
            {messages.length === 0 && (
              <p className="py-8 text-center text-sm text-muted">
                Ask a follow-up about your market, risks, MVP, or launch strategy.
              </p>
            )}
            {messages.map((item, index) => (
              <div
                key={index}
                className={`flex ${item.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <p
                  className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                    item.role === 'user'
                      ? 'bg-accent text-white'
                      : 'border border-border bg-surface text-text'
                  }`}
                >
                  {item.text}
                </p>
              </div>
            ))}
            {isSubmitting && (
              <div className="flex justify-start">
                <p className="rounded-xl border border-border bg-surface px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-muted cursor-blink">
                  Advisor is thinking
                </p>
              </div>
            )}
            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-danger/20 bg-danger/5 p-3 text-sm text-danger" role="alert">
                <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border p-4">
            <label htmlFor="advisor-message" className="sr-only">Message the validation advisor</label>
            <input
              id="advisor-message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              maxLength={1200}
              placeholder="What should I validate first?"
              disabled={isSubmitting}
              className="min-w-0 flex-1 rounded-full border border-border bg-surface px-4 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-accent disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={isSubmitting || !input.trim()}
              className="shrink-0 rounded-full bg-accent px-5 py-2.5 font-mono text-xs font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
            >
              Send
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => (isOpen ? setIsOpen(false) : openPanel())}
        aria-label={isOpen ? 'Close validation advisor chat' : 'Open validation advisor chat'}
        aria-expanded={isOpen}
        className="relative flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg transition-transform hover:scale-105 hover:bg-accent-hover"
      >
        {isOpen ? <IconX className="h-6 w-6" /> : <IconMessageCircle className="h-6 w-6" />}
        {!isOpen && unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1 font-mono text-[10px] font-semibold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
    </div>
  )
}
