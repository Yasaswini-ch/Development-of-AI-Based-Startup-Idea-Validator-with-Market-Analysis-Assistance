import { useEffect, useRef, useState } from 'react'
import {
  IconAlertTriangle,
  IconCheckCircle,
  IconGlobe,
  IconLightbulb,
  IconMessageCircle,
  IconUsers,
  IconX,
} from './icons'

const MAX_MESSAGES = 40
const SUGGESTED_QUESTIONS = [
  { text: 'What should I validate first?', Icon: IconLightbulb },
  { text: "What's the biggest risk here?", Icon: IconAlertTriangle },
  { text: 'What should the MVP include?', Icon: IconCheckCircle },
  { text: 'How should I launch this?', Icon: IconGlobe },
]
// Shown under the advisor's latest reply so the conversation has an obvious
// next step instead of a dead end - generic rather than reply-specific since
// there's no backend support (yet) for suggesting follow-ups grounded in the
// actual answer just given.
const FOLLOWUP_QUESTIONS = [
  'Can you say more about that?',
  "What's the risk in that approach?",
  'What would you do first?',
  'Is there evidence for that?',
]

// The advisor is prompted to answer as a short lead line plus "- " bullet
// points with **bold** on key terms (see chat_graph.py's _build_response_crew)
// instead of one dense paragraph - this renders that lightweight structure
// instead of dumping it as a single wall-of-text <p> with literal asterisks
// and dashes showing.
function renderInline(text, keyPrefix) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      <strong key={`${keyPrefix}-${i}`} className="font-semibold text-inherit">
        {part.slice(2, -2)}
      </strong>
    ) : (
      <span key={`${keyPrefix}-${i}`}>{part}</span>
    ),
  )
}

function parseBlocks(text) {
  const blocks = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const bullet = line.match(/^[-•]\s+(.*)/)
    if (bullet) {
      const last = blocks[blocks.length - 1]
      if (last?.type === 'list') last.items.push(bullet[1])
      else blocks.push({ type: 'list', items: [bullet[1]] })
    } else {
      blocks.push({ type: 'p', text: line })
    }
  }
  return blocks
}

function MessageContent({ text }) {
  const blocks = parseBlocks(text)
  return (
    <div className="space-y-1.5">
      {blocks.map((block, i) =>
        block.type === 'list' ? (
          <ul key={i} className="list-disc space-y-1 pl-4">
            {block.items.map((item, j) => (
              <li key={j}>{renderInline(item, `${i}-${j}`)}</li>
            ))}
          </ul>
        ) : (
          <p key={i}>{renderInline(block.text, `${i}`)}</p>
        ),
      )}
    </div>
  )
}

function Avatar({ role }) {
  const Icon = role === 'user' ? IconUsers : IconLightbulb
  return (
    <span
      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
        role === 'user' ? 'bg-border text-muted' : 'bg-accent/10 text-accent'
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
    </span>
  )
}

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
  const inputRef = useRef(null)
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

  function fillSuggestion(question) {
    setInput(question)
    inputRef.current?.focus()
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
        <section className="flex w-[calc(100vw-2.5rem)] max-w-md flex-col overflow-hidden rounded-2xl border border-border bg-panel shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="flex items-center gap-2 font-serif text-lg text-text">
              <IconLightbulb className="h-5 w-5 text-accent" />
              Validation advisor
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-info" aria-hidden="true" />
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
            className="max-h-96 min-h-48 space-y-3 overflow-y-auto bg-surface/40 px-5 py-4"
            aria-live="polite"
          >
            {messages.length === 0 && (
              <div className="flex flex-col items-center py-6 text-center">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent/10 text-accent">
                  <IconLightbulb className="h-4 w-4" />
                </span>
                <p className="mt-3 max-w-[220px] text-sm leading-relaxed text-muted">
                  Ask a follow-up about your market, risks, MVP, or launch strategy.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                  {SUGGESTED_QUESTIONS.map(({ text, Icon }) => (
                    <button
                      key={text}
                      type="button"
                      onClick={() => fillSuggestion(text)}
                      className="flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text shadow-sm transition-colors hover:border-accent hover:text-accent"
                    >
                      <Icon className="h-3 w-3 text-accent" />
                      {text}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((item, index) => (
              <div
                key={index}
                className={`flex items-end gap-2 ${item.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <Avatar role={item.role} />
                <div
                  className={`max-w-[78%] rounded-xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
                    item.role === 'user'
                      ? 'bg-accent text-white'
                      : 'border border-border bg-surface text-text'
                  }`}
                >
                  <MessageContent text={item.text} />
                </div>
              </div>
            ))}
            {isSubmitting && (
              <div className="flex items-end gap-2">
                <Avatar role="advisor" />
                <p className="rounded-xl border border-border bg-surface px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-muted shadow-sm cursor-blink">
                  Advisor is thinking
                </p>
              </div>
            )}
            {!isSubmitting && messages.length > 0 && messages[messages.length - 1].role === 'advisor' && (
              <div className="flex flex-wrap gap-1.5 pl-8">
                {FOLLOWUP_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => fillSuggestion(question)}
                    className="rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-accent hover:text-accent"
                  >
                    {question}
                  </button>
                ))}
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
              ref={inputRef}
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
