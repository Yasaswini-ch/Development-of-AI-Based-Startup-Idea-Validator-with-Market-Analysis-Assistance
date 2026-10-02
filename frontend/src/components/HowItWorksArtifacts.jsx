import { useEffect, useState } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { IconCheckCircle } from './icons'

// Small, purely illustrative previews shown beside each "How it works" step.
// Nothing here calls the backend and the content is sample text, not real
// results - the frame says so. They loop so the section feels alive, and hold
// a still, finished frame for visitors who prefer reduced motion.

function prefersReducedMotion() {
  return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

// Cycles 0..length (one extra beat at the end so the finished state is held
// before the loop restarts). Reduced motion pins it to the finished state.
function useLoopStep(length, ms) {
  const reduced = prefersReducedMotion()
  const [step, setStep] = useState(reduced ? length : 0)
  useEffect(() => {
    if (reduced) return undefined
    const id = setInterval(() => setStep((s) => (s + 1) % (length + 1)), ms)
    return () => clearInterval(id)
  }, [length, ms, reduced])
  return step
}

function Frame({ caption, children }) {
  return (
    <div aria-hidden="true" className="rounded-xl border border-border bg-surface p-3.5">
      <div className="mb-2.5 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{caption}</span>
        <span className="rounded-full border border-border-strong px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted">
          Sample
        </span>
      </div>
      {children}
    </div>
  )
}

const FORM_IDEA = ['A tool that turns support calls into a weekly feedback digest']

function FormArtifact() {
  const { text } = useTypewriter(FORM_IDEA)
  const reduced = prefersReducedMotion()
  const idea = reduced ? FORM_IDEA[0] : text
  return (
    <Frame caption="The form">
      <div className="space-y-2">
        <div className="rounded-lg border border-border bg-panel px-2.5 py-2 text-xs text-text">
          <span className="block font-mono text-[9px] uppercase tracking-widest text-muted">Startup idea</span>
          <span className={`mt-0.5 block min-h-[2.4em] leading-snug ${reduced ? '' : 'cursor-blink'}`}>{idea}</span>
        </div>
        <div className="rounded-lg border border-border bg-panel px-2.5 py-2 text-xs text-text">
          <span className="block font-mono text-[9px] uppercase tracking-widest text-muted">Target customer</span>
          <span className="mt-0.5 block">Support teams at SaaS companies</span>
        </div>
        <div className="rounded-lg border border-border bg-panel px-2.5 py-2 text-xs text-text">
          <span className="block font-mono text-[9px] uppercase tracking-widest text-muted">Problem</span>
          <span className="mt-0.5 block">Customer feedback gets lost between calls</span>
        </div>
        <div className="rounded-full bg-accent px-3 py-1.5 text-center font-mono text-[10px] font-semibold uppercase tracking-wide text-white">
          Validate startup idea →
        </div>
      </div>
    </Frame>
  )
}

const RESEARCH_STAGES = [
  'Search the web across 5 angles',
  'Size the market',
  'Find competitors',
  'Score viability',
  'Draft MVP and go-to-market',
]

function ResearchArtifact() {
  const step = useLoopStep(RESEARCH_STAGES.length, 1100)
  return (
    <Frame caption="A run, stage by stage">
      <ul className="space-y-2">
        {RESEARCH_STAGES.map((label, i) => {
          const done = i < step
          const current = i === step
          return (
            <li key={label} className="flex items-center gap-2.5 text-xs">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                {done ? (
                  <IconCheckCircle className="h-4 w-4 text-success" />
                ) : current ? (
                  <span className="pulse-dot h-2.5 w-2.5 rounded-full bg-accent" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-border-strong" />
                )}
              </span>
              <span className={done ? 'text-text' : current ? 'font-medium text-text' : 'text-muted/70'}>{label}</span>
            </li>
          )
        })}
      </ul>
    </Frame>
  )
}

function VerdictArtifact() {
  const reduced = prefersReducedMotion()
  const [filled, setFilled] = useState(reduced)
  useEffect(() => {
    if (reduced) return undefined
    const id = setTimeout(() => setFilled(true), 80)
    return () => clearTimeout(id)
  }, [reduced])
  return (
    <Frame caption="The verdict">
      <div className="flex items-center justify-between gap-2">
        <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-accent">
          Validate first
        </span>
        <span className="font-serif text-lg font-semibold text-text">
          62<span className="font-mono text-[10px] font-normal text-muted">/100</span>
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-1000 ease-out"
          style={{ width: filled ? '62%' : '0%' }}
        />
      </div>
      <ul className="mt-3 space-y-2">
        <li className="rounded-lg border border-border bg-panel p-2 text-xs leading-snug text-text">
          Support leaders already pay for call analytics.
          <span className="mt-1.5 flex gap-1.5">
            <span className="rounded border border-success/40 bg-success/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-success">
              Grounded
            </span>
            <span className="rounded border border-border-strong px-1.5 py-0.5 font-mono text-[9px] text-muted">src-3</span>
          </span>
        </li>
        <li className="rounded-lg border border-border bg-panel p-2 text-xs leading-snug text-text">
          Weekly digests would reduce churn.
          <span className="mt-1.5 flex gap-1.5">
            <span className="rounded border border-border-strong bg-surface px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-muted-strong">
              Inferred
            </span>
          </span>
        </li>
      </ul>
    </Frame>
  )
}

function ChatArtifact() {
  const step = useLoopStep(3, 1800)
  return (
    <Frame caption="The advisor">
      <div className="space-y-2 text-xs leading-snug">
        <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-3 py-1.5 text-white">
          What&apos;s my riskiest assumption?
        </div>
        {step === 1 && (
          <div className="flex w-fit gap-1 rounded-2xl rounded-bl-sm border border-border bg-panel px-3 py-2">
            {[0, 1, 2].map((d) => (
              <span key={d} className="pulse-dot h-1.5 w-1.5 rounded-full bg-muted" style={{ animationDelay: `${d * 200}ms` }} />
            ))}
          </div>
        )}
        {step >= 2 && (
          <div className="fade-in-up w-fit max-w-[90%] rounded-2xl rounded-bl-sm border border-border bg-panel px-3 py-1.5 text-text">
            That buyers will pay for it. Run 10 problem interviews before you build anything.
          </div>
        )}
      </div>
    </Frame>
  )
}

export { FormArtifact, ResearchArtifact, VerdictArtifact, ChatArtifact }
