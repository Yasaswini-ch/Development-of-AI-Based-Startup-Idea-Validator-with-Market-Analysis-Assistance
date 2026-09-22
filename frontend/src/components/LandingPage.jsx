import useTypewriter from '../hooks/useTypewriter'
import useCountUp from '../hooks/useCountUp'
import ConfidenceGauge from './ConfidenceGauge'
import {
  IconLightbulb,
  IconGlobe,
  IconCheckCircle,
  IconMessageCircle,
} from './icons'

const EXAMPLE_IDEAS = [
  'An AI copilot that drafts investor updates from raw metrics',
  'A marketplace for local plant swaps between neighbors',
  'A subscription box for home baristas',
  'A tool that turns support calls into a weekly feedback digest',
]

const STEPS = [
  {
    Icon: IconLightbulb,
    title: 'Describe your idea',
    body: 'Your idea, target customer, and the problem it solves — one short form, no signup.',
  },
  {
    Icon: IconGlobe,
    title: 'Multi-agent live research',
    body: 'Five agents search the web in parallel for market size, competitors, and real demand.',
  },
  {
    Icon: IconCheckCircle,
    title: 'A confidence score, not a guess',
    body: 'Every claim is grounded in a real, clickable source — including a SWOT, MVP plan, and go-to-market.',
  },
  {
    Icon: IconMessageCircle,
    title: 'Ask a follow-up',
    body: 'A validation advisor is on hand to dig into risks, pricing, or what to build first.',
  },
]

export default function LandingPage({ onStart }) {
  const { text, settled } = useTypewriter(EXAMPLE_IDEAS)
  const confidence = useCountUp(settled ? 84 : 0, 900)

  return (
    <div className="min-h-screen bg-surface">
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-10 sm:pt-14">
        <div className="mb-14 flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-widest text-accent">Affinity</p>
          <span className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-accent">
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
            Live
          </span>
        </div>

        <section className="fade-in-up text-center">
          <p className="mb-3 font-mono text-xs uppercase tracking-widest text-muted">
            AI Market Research Agent
          </p>
          <h1 className="font-serif text-5xl leading-tight text-text sm:text-6xl">
            Before you build it,
            <br />
            measure the <em className="text-accent italic">affinity</em>.
          </h1>
          <p className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-muted">
            Describe a startup idea and a team of research agents will search the live web,
            score its opportunity, and hand you a grounded, source-cited validation report —
            in minutes, not days.
          </p>

          <div className="mt-8 flex flex-col items-center gap-2.5">
            <button
              type="button"
              onClick={onStart}
              className="rounded-full bg-accent px-7 py-3 font-mono text-sm font-semibold uppercase tracking-wide text-white shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-accent-hover"
            >
              Test it out →
            </button>
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted">
              No signup · Free to try
            </p>
          </div>
        </section>

        <section
          className="fade-in-up mt-14 rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-7"
          style={{ animationDelay: '150ms' }}
        >
          <div className="flex flex-wrap items-center gap-6">
            <div className="min-w-0 flex-1">
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
                Startup idea
              </p>
              <p className="font-serif text-lg leading-snug text-text cursor-blink min-h-[3.5rem]">
                {text}
              </p>
              <div
                className={`mt-3 flex items-center gap-2 border-t border-border pt-3 font-mono text-xs uppercase tracking-wide transition-opacity duration-300 ${
                  settled ? 'text-accent opacity-100' : 'text-muted opacity-0'
                }`}
              >
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
                Validating live sources…
              </div>
            </div>
            <ConfidenceGauge percent={confidence} size={92} />
          </div>
        </section>

        <section className="mt-16">
          <p
            className="fade-in-up mb-6 text-center font-mono text-xs uppercase tracking-widest text-muted"
            style={{ animationDelay: '200ms' }}
          >
            How it works
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {STEPS.map(({ Icon, title, body }, i) => (
              <div
                key={title}
                className="fade-in-up flex gap-3.5 rounded-2xl border border-border bg-panel p-5 shadow-sm"
                style={{ animationDelay: `${250 + i * 100}ms` }}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                  <Icon className="h-[18px] w-[18px]" />
                </span>
                <div>
                  <h3 className="font-serif text-base font-semibold text-text">
                    {i + 1}. {title}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div
          className="fade-in-up mt-14 flex justify-center"
          style={{ animationDelay: '650ms' }}
        >
          <button
            type="button"
            onClick={onStart}
            className="rounded-full border border-border px-6 py-2.5 font-mono text-xs uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
          >
            Test it out →
          </button>
        </div>

        <p className="mt-14 text-center font-mono text-xs uppercase tracking-widest text-muted">
          Multi-agent · Live Web Search
        </p>
      </main>
    </div>
  )
}
