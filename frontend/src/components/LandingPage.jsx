import useTypewriter from '../hooks/useTypewriter'
import GoogleSignInButton from './GoogleSignInButton'
import useAuthRequest from '../hooks/useAuthRequest'
import { DECISION_STYLES } from './VerdictCard'
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

const STEPS = [
  {
    Icon: IconLightbulb,
    title: 'Describe your idea',
    body: 'Your idea, target customer, and the problem it solves — one short form, no signup.',
  },
  {
    Icon: IconGlobe,
    title: 'Multi-agent live research',
    body: 'A team of research agents search the web in parallel for market size, competitors, and real demand.',
  },
  {
    Icon: IconCheckCircle,
    title: 'A verdict, not a guess',
    body: 'Pursue, validate first, or rethink — with every claim showing its evidence, and anything unsourced labelled as inference.',
  },
  {
    Icon: IconMessageCircle,
    title: 'Ask a follow-up',
    body: 'A validation advisor is on hand to dig into risks, pricing, or what to build first.',
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

export default function LandingPage({ onStart, currentUser, onSignIn, onSignOut, apiUrl, onAuthenticated }) {
  const { text, settled, index } = useTypewriter(EXAMPLE_IDEAS.map((e) => e.idea))
  const demo = EXAMPLE_IDEAS[index]
  const demoStyle = DECISION_STYLES[demo.decision] || DECISION_STYLES.validate_first
  const google = useAuthRequest(apiUrl, onAuthenticated)

  function handleGoogleCredential(idToken) {
    google.submit('/auth/google', { idToken }, 'Google sign-in failed. Please try again.')
  }

  return (
    <div className="min-h-screen bg-surface">
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-10 sm:pt-14">
        <div className="mb-14 flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-widest text-accent">Affinity</p>
          <div className="flex items-center gap-2">
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

        <section className="fade-in-up mx-auto max-w-xl text-center">
          <p className="mb-3 font-mono text-xs uppercase tracking-widest text-muted">
            AI Market Research Agent
          </p>
          <h1 className="font-serif text-4xl leading-tight text-text sm:text-6xl">
            Before you build it, measure the{' '}
            <em className="text-accent italic">affinity</em>.
          </h1>
          <p className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-muted">
            Describe a startup idea and a team of research agents will search the live web,
            score its opportunity, and hand you a grounded, source-cited validation report —
            in minutes, not days.
          </p>

          <div className="mt-8 flex flex-col items-center gap-2.5">
            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={onStart}
                className="rounded-full bg-accent px-7 py-3 font-mono text-sm font-semibold uppercase tracking-wide text-white shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-accent-hover"
              >
                Validate my idea →
              </button>
            </div>
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

        <section className="mt-16">
          <p
            className="fade-in-up mb-6 text-center font-mono text-xs uppercase tracking-widest text-muted"
            style={{ animationDelay: '200ms' }}
          >
            How it works
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

        <section className="mt-16">
          <p
            className="fade-in-up mb-2 text-center font-mono text-xs uppercase tracking-widest text-muted"
            style={{ animationDelay: '250ms' }}
          >
            Five pillars of evidence
          </p>
          <h2
            className="fade-in-up mb-8 text-center font-serif text-2xl text-text"
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
