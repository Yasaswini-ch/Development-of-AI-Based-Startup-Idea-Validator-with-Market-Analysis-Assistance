import { useState } from 'react'
import { AGENTS } from './agentsData'
import useTypewriter from '../hooks/useTypewriter'
import GoogleSignInButton from './GoogleSignInButton'
import useAuthRequest from '../hooks/useAuthRequest'
import { DECISION_STYLES } from './VerdictCard'
import HeroOllie from './HeroOllie'
import PipelineShowcase from './PipelineShowcase'
import PlayableVerdict from './PlayableVerdict'
import ReceiptsStrip from './ReceiptsStrip'
import { FormArtifact, ResearchArtifact, VerdictArtifact, ChatArtifact } from './HowItWorksArtifacts'
import AgentsGrid from './AgentsGrid'
import TechStack from './TechStack'
import SampleReportPreview from './SampleReportPreview'
import ComparisonTable from './ComparisonTable'
import {
  IconLightbulb,
  IconGlobe,
  IconCheckCircle,
  IconMessageCircle,
  IconUser,
  IconListChecks,
  IconColumns,
  IconDownload,
  IconTrendingUp,
  IconFlag,
  IconNewspaper,
} from './icons'

// Each example idea pairs with a canned verdict so the hero demo previews
// what the report actually opens with (VerdictCard) instead of a bare
// confidence percentage - including a "rethink", so the demo doesn't imply
// every idea gets a pass.
const EXAMPLE_IDEAS = [
  {
    idea: 'An AI copilot that drafts investor updates from raw metrics',
    decision: 'validate_first',
    label: 'Validate first',
    score: 62,
    scoreName: 'Market viability',
    reason: 'Real demand from early-stage founders, but pricing power is still unproven.',
  },
  {
    idea: 'A marketplace for local plant swaps between neighbors',
    decision: 'rethink',
    label: 'Rethink',
    score: 34,
    scoreName: 'Market viability',
    reason: 'Search volume and willingness to pay are both weak in the sources found.',
  },
  {
    idea: 'A subscription box for home baristas',
    decision: 'validate_first',
    label: 'Validate first',
    score: 58,
    scoreName: 'Market viability',
    reason: 'Crowded category — the wedge depends on one untested retention claim.',
  },
  {
    idea: 'A tool that turns support calls into a weekly feedback digest',
    decision: 'pursue',
    label: 'Pursue',
    score: 78,
    scoreName: 'Market viability',
    reason: 'Corroborated demand across multiple sources and no unmitigated high risk.',
  },
]

// Each step has a short teaser (shown on the step button) plus the detail
// shown when it's selected: `flow` is what actually runs, in order, and
// `tags` are the real tools behind it. Keep these in sync with the pipeline
// in backend/agent/graph.py - they are claims about the product.
// One illustrative preview per step, in the same order as STEPS.
const STEP_ARTIFACTS = [FormArtifact, ResearchArtifact, VerdictArtifact, ChatArtifact]

const STEPS = [
  {
    Icon: IconLightbulb,
    title: 'Describe your idea',
    body: 'Your idea, target customer, and the problem it solves — one short form, no signup.',
    summary:
      'Three fields and one click. Nothing to install, no account needed to try it; sign in only if you want your history saved.',
    flow: [
      'Your idea, customer and problem are sent to the validation API',
      'Input is length-checked and rate-limited before anything runs',
      'The idea is expanded into five search angles: market size, competitors, customer demand, industry news, existing solutions',
    ],
    tags: ['React 19', 'Tailwind 4', 'FastAPI', 'Pydantic', 'Per-IP rate limits'],
  },
  {
    Icon: IconGlobe,
    title: 'Multi-agent live research',
    body: 'A team of research agents search the web in parallel for market size, competitors, and real demand.',
    summary:
      'A pipeline of specialised agents shares one evidence base. Each stage reads what the stages before it found, so nothing is invented from thin air.',
    flow: [
      'Live web search across all five angles, with duplicates and low-signal sites filtered out',
      'Market agent sizes the opportunity and builds customer segments',
      'Competitor discovery finds rivals, then enriches them from Wikidata and the App Store',
      'Whitespace, SWOT and viability are computed from the same evidence',
      'MVP and go-to-market plans are written in parallel',
    ],
    tags: ['LangGraph', 'CrewAI', 'Tavily', 'DuckDuckGo', 'spaCy NER', 'Groq', 'Gemini fallback', 'Wikidata'],
    note: 'If a model is rate-limited the next one takes over; if every model fails, that section falls back to evidence-only text and is labelled as such.',
  },
  {
    Icon: IconCheckCircle,
    title: 'A verdict, not a guess',
    body: 'Pursue, validate first, or rethink — with every claim showing its evidence, and anything unsourced labelled as inference.',
    summary:
      'The report separates what the sources say from what the model inferred, and shows you how much to trust the result.',
    flow: [
      'Every claim carries the ids of the sources behind it; ids the model invents are dropped',
      'Claims are tagged Grounded (traced to a source) or Inferred',
      'A confidence dashboard scores source coverage, cross-source agreement and relevance',
      'A contradiction check flags places where sections disagree with each other',
      'You get a verdict and a 0 to 100 viability score, with the reasons',
    ],
    tags: ['Source citations', 'Grounded vs Inferred', 'Confidence dashboard', 'Contradiction check', 'Viability score'],
  },
  {
    Icon: IconMessageCircle,
    title: 'Ask a follow-up',
    body: 'Ollie, our validation advisor, is on hand to dig into risks, pricing, or what to build first.',
    summary:
      'Keep going after the report: ask about a risk, a price point or what to build first, and take the report with you.',
    flow: [
      'The advisor answers from your report’s own evidence',
      'It searches the web again only when a question needs fresh data',
      'Pivots and decisions are remembered without resending the whole chat',
      'Export a PDF dossier, email the report, or compare saved ideas side by side',
    ],
    tags: ['LangGraph chat graph', 'Gemini', 'Session memory', 'ReportLab PDF', 'Email delivery'],
  },
]

// The five evidence pillars behind the report, in the order they appear -
// this is what actually differentiates the output, so it replaces a grid
// of generic app features on the landing page.
const PILLARS = [
  {
    Icon: IconMessageCircle,
    title: 'Voice of the market',
    body: 'Real customer quotes pulled from the live web, each one tied back to its source.',
  },
  {
    Icon: IconTrendingUp,
    title: 'Market viability index',
    body: 'One score built from the dynamics behind it, not a single black-box number.',
  },
  {
    Icon: IconNewspaper,
    title: 'Competitors & white space',
    body: 'Who else is already there, and where the gap actually is.',
  },
  {
    Icon: IconFlag,
    title: 'Strategic wedge',
    body: 'The angle to enter on, scored across five vectors — not just "differentiate".',
  },
  {
    Icon: IconListChecks,
    title: 'GTM & MVP roadmap',
    body: 'What to build, sell, and test first, stage by stage.',
  },
]

// Account features, kept short since they support the report rather than
// being the reason to trust it.
const ACCOUNT_PERKS = [
  { Icon: IconUser, text: 'Your own board — every validation follows your account' },
  { Icon: IconColumns, text: 'Compare up to five ideas side by side' },
  { Icon: IconDownload, text: 'Export a PDF or email yourself the full report' },
]

const NAV_LINKS = [
  { href: '#what-you-get', label: 'What you get' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#watch-it-work', label: 'Watch it work' },
  { href: '#try-the-verdict', label: 'Verdict' },
  { href: '#receipts', label: 'Receipts' },
  { href: '#agents', label: 'Agents' },
  { href: '#why-affinity', label: 'Why Affinity' },
]

export default function LandingPage({ onStart, currentUser, onSignIn, onSignOut, apiUrl, onAuthenticated }) {
  const { text, settled, index } = useTypewriter(EXAMPLE_IDEAS.map((e) => e.idea))
  const demo = EXAMPLE_IDEAS[index]
  const demoStyle = DECISION_STYLES[demo.decision] || DECISION_STYLES.validate_first
  const google = useAuthRequest(apiUrl, onAuthenticated)
  const [activeStep, setActiveStep] = useState(0)
  const [heroIdea, setHeroIdea] = useState('')
  const step = STEPS[activeStep]
  const StepArtifact = STEP_ARTIFACTS[activeStep]

  // Arrow keys move between steps, as with any tab list.
  function handleStepKeyDown(e) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = (activeStep + (e.key === 'ArrowRight' ? 1 : -1) + STEPS.length) % STEPS.length
    setActiveStep(next)
    document.getElementById(`how-step-${next}`)?.focus()
  }

  function handleGoogleCredential(idToken) {
    google.submit('/auth/google', { idToken }, 'Google sign-in failed. Please try again.')
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-2.5">
          <a href="#top" className="flex shrink-0 items-center gap-2.5 font-serif text-2xl font-semibold tracking-tight text-text" aria-label="Affinity, back to top">
            <img src={`${import.meta.env.BASE_URL}logo.png`} alt="" className="h-9 w-9 object-contain" />
            Affinity
          </a>
          <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map(({ href, label }) => (
              <a
                key={href}
                href={href}
                className="rounded-full px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wide text-muted-strong transition-colors hover:bg-panel hover:text-accent"
              >
                {label}
              </a>
            ))}
          </nav>
          <div className="flex shrink-0 items-center gap-2">
            {currentUser ? (
              <button
                type="button"
                onClick={onSignOut}
                title={`Signed in as ${currentUser.email} - click to sign out`}
                className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
              >
                <IconUser className="h-3 w-3 text-accent" />
                <span className="max-w-[9rem] truncate normal-case">{currentUser.email}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onSignIn}
                className="rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
              >
                Sign in
              </button>
            )}
          </div>
        </div>
        <nav aria-label="Sections (compact)" className="flex gap-1 overflow-x-auto border-t border-border px-3 py-1.5 md:hidden">
          {NAV_LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className="shrink-0 rounded-full px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wide text-muted-strong hover:bg-panel hover:text-accent"
            >
              {label}
            </a>
          ))}
        </nav>
      </header>

      <main id="top" className="mx-auto max-w-5xl px-4 pb-16 pt-10 sm:pt-14">
        <section className="fade-in-up mx-auto max-w-xl text-center">
          <p className="font-tagline mb-3 text-base font-semibold text-accent sm:text-lg">
            Curious? So are our agents.
          </p>
          <h1 className="font-serif text-4xl leading-tight text-text sm:text-6xl">
            <span className="relative inline-block">
              B
              <HeroOllie />
            </span>
            efore you build it, measure the{' '}
            <em className="text-accent italic">affinity</em>.
          </h1>
          <p className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-muted-strong">
            Describe a startup idea and a team of research agents will search the live web,
            score its opportunity, and hand you a grounded, source-cited validation report —
            in minutes, not days.
          </p>

          <div className="mt-8 flex flex-col items-center gap-2.5">
            <form
              className="w-full max-w-md"
              onSubmit={(e) => {
                e.preventDefault()
                onStart(heroIdea.trim())
              }}
            >
              <label htmlFor="hero-idea" className="sr-only">
                Your startup idea
              </label>
              <textarea
                id="hero-idea"
                rows={2}
                maxLength={2000}
                value={heroIdea}
                onChange={(e) => setHeroIdea(e.target.value)}
                placeholder="Describe your idea in a sentence or two…"
                className="w-full resize-none rounded-2xl border border-border bg-panel px-4 py-3 text-left text-sm leading-relaxed text-text shadow-sm outline-none transition-colors placeholder:text-muted focus:border-accent"
              />
              <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="submit"
                  className="rounded-full bg-accent px-7 py-3 font-mono text-sm font-semibold uppercase tracking-wide text-white shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-accent-hover"
                >
                  Validate my idea →
                </button>
              </div>
            </form>
            {!currentUser && apiUrl && onAuthenticated && (
              <div className="mt-1 flex w-full max-w-xs flex-col items-center">
                <div className={`w-full ${google.isSubmitting ? 'pointer-events-none opacity-60' : ''}`} aria-busy={google.isSubmitting}>
                  <GoogleSignInButton onCredential={handleGoogleCredential} onError={google.setError} width={320} />
                </div>
                {google.isSubmitting && (
                  <p className="mt-2 text-center font-mono text-[11px] uppercase tracking-wide text-muted">
                    {google.isWaking ? 'Waking up the server, this can take up to a minute…' : 'Signing you in…'}
                  </p>
                )}
                {google.error && (
                  <p className="mt-2 text-center text-[11px] text-danger" role="alert">{google.error}</p>
                )}
              </div>
            )}
            <p className="text-[13px] text-muted">
              {currentUser ? 'Signed in · Your validations are saved to your account' : 'No signup required to try · Sign in to save your history'}
            </p>
            <ul aria-label="What you get" className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5 font-mono text-[11px] uppercase tracking-wide text-muted-strong">
              <li>{AGENTS.length} agents and engines</li>
              <li>Every claim Grounded or Inferred</li>
              <li>PDF and email report</li>
            </ul>
          </div>

        </section>

        <section
          className={`fade-in-up mx-auto mt-14 max-w-2xl rounded-2xl border-[1.5px] bg-panel p-6 shadow-sm transition-colors duration-300 sm:p-7 ${settled ? demoStyle.border : 'border-border'}`}
          style={{ animationDelay: '150ms' }}
        >
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
            Startup idea
          </p>
          <p className="font-serif text-lg leading-snug text-text cursor-blink min-h-[3.5rem]">
            {text}
          </p>
          <div
            className={`mt-3 flex items-start justify-between gap-4 border-t border-border pt-3 transition-opacity duration-300 ${
              settled ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <div className="min-w-0 flex-1">
              <span
                className={`whitespace-nowrap rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wide ${demoStyle.badge}`}
              >
                {demo.label}
              </span>
              <span className="ml-2 text-sm leading-relaxed text-muted-strong">{demo.reason}</span>
            </div>
            <p className="shrink-0 font-serif text-2xl leading-none text-text">
              {demo.score}
              <span className="ml-0.5 font-mono text-xs text-muted">/100</span>
            </p>
          </div>
        </section>

        <SampleReportPreview />

        <section id="how-it-works" className="mt-16 scroll-mt-24">
          <p
            className="fade-in-up mb-2 text-center font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent"
            style={{ animationDelay: '200ms' }}
          >
            How it works
          </p>
          <h2 className="fade-in-up mb-6 text-center font-serif text-2xl font-semibold text-text sm:text-3xl" style={{ animationDelay: '220ms' }}>
            From idea to verdict in four steps.
          </h2>
          <div
            role="tablist"
            aria-label="How it works"
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
            onKeyDown={handleStepKeyDown}
          >
            {STEPS.map(({ Icon, title, body }, i) => {
              const active = i === activeStep
              return (
                <button
                  key={title}
                  id={`how-step-${i}`}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-controls="how-step-panel"
                  tabIndex={active ? 0 : -1}
                  onClick={() => setActiveStep(i)}
                  className={`fade-in-up flex gap-3.5 rounded-2xl border p-4 text-left shadow-sm transition-all duration-200 ${
                    active
                      ? 'border-accent bg-accent/5 ring-1 ring-accent/30'
                      : 'border-border bg-panel hover:-translate-y-0.5 hover:border-accent/50'
                  }`}
                  style={{ animationDelay: `${250 + i * 100}ms` }}
                >
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors ${
                      active ? 'bg-accent text-white' : 'bg-accent/10 text-accent'
                    }`}
                  >
                    <Icon className="h-[18px] w-[18px]" />
                  </span>
                  <span>
                    <span className="block font-serif text-base font-semibold text-text">
                      {i + 1}. {title}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-muted">{body}</span>
                  </span>
                </button>
              )
            })}
          </div>

          <div
            key={activeStep}
            id="how-step-panel"
            role="tabpanel"
            aria-labelledby={`how-step-${activeStep}`}
            className="fade-in-up mt-4 grid gap-6 rounded-2xl border border-border bg-panel p-6 shadow-sm md:grid-cols-[1.4fr_1fr]"
          >
            <div>
              <p className="font-mono text-[11px] uppercase tracking-widest text-accent">
                Step {activeStep + 1} of {STEPS.length}
              </p>
              <h3 className="mt-1 font-serif text-xl font-semibold text-text">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{step.summary}</p>

              <p className="mt-5 font-mono text-[11px] uppercase tracking-widest text-muted">What runs, in order</p>
              <ol className="mt-3 space-y-3">
                {step.flow.map((line, n) => (
                  <li key={line} className="flex gap-3 text-sm leading-relaxed text-text">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/10 font-mono text-[10px] font-semibold text-accent">
                      {n + 1}
                    </span>
                    <span>{line}</span>
                  </li>
                ))}
              </ol>
            </div>

            <div>
              <StepArtifact />
              <p className="mt-5 font-mono text-[11px] uppercase tracking-widest text-muted">Under the hood</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {step.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-border-strong bg-surface px-2.5 py-1 font-mono text-[11px] font-medium text-muted-strong"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              {step.note && (
                <p className="mt-4 rounded-xl border border-accent/30 bg-accent/5 p-3 text-xs leading-relaxed text-text">
                  <span className="font-semibold text-accent">Safety net. </span>
                  {step.note}
                </p>
              )}
            </div>
          </div>
        </section>

        <PipelineShowcase />

        <PlayableVerdict />

        <ReceiptsStrip />

        <section className="mt-16">
          <p
            className="fade-in-up mb-2 text-center font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent"
            style={{ animationDelay: '250ms' }}
          >
            Five pillars of evidence
          </p>
          <h2
            className="fade-in-up mb-8 text-center font-serif text-2xl font-semibold text-text sm:text-3xl"
            style={{ animationDelay: '300ms' }}
          >
            Built for founders who want proof, not vibes.
          </h2>
          <div className="fade-in-up grid gap-x-8 gap-y-6 rounded-2xl border border-border bg-panel p-6 sm:grid-cols-2 sm:p-8 lg:grid-cols-3" style={{ animationDelay: '350ms' }}>
            {PILLARS.map(({ Icon, title, body }) => (
              <div key={title} className="flex gap-3">
                <Icon className="mt-0.5 h-[18px] w-[18px] shrink-0 text-accent" />
                <div>
                  <h3 className="font-serif text-base font-semibold text-text">{title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
                </div>
              </div>
            ))}
          </div>
          <div
            className="fade-in-up mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 rounded-2xl border border-border bg-panel/60 px-6 py-4"
            style={{ animationDelay: '400ms' }}
          >
            {ACCOUNT_PERKS.map(({ Icon, text }) => (
              <span key={text} className="flex items-center gap-2 text-[13px] text-muted-strong">
                <Icon className="h-[15px] w-[15px] shrink-0 text-accent" />
                {text}
              </span>
            ))}
          </div>
        </section>

        <AgentsGrid />

        <TechStack />

        <ComparisonTable />

        <div
          className="fade-in-up mt-14 flex flex-col items-center gap-2"
          style={{ animationDelay: '650ms' }}
        >
          <button
            type="button"
            onClick={onStart}
            className="rounded-full bg-accent px-7 py-3 font-mono text-sm font-semibold uppercase tracking-wide text-white shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-accent-hover"
          >
            Validate my idea →
          </button>
          <p className="text-[13px] text-muted">Free to try · Full report in minutes</p>
        </div>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-2 px-4 py-8 text-center sm:flex-row sm:justify-between sm:text-left">
          <p className="font-mono text-xs uppercase tracking-widest text-muted">
            Affinity · Multi-agent · Live Web Search
          </p>
          <p className="font-mono text-[11px] uppercase tracking-widest text-muted/70">
            © {new Date().getFullYear()} Affinity
          </p>
        </div>
      </footer>
    </div>
  )
}
