import { useState } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import useCountUp from '../hooks/useCountUp'
import ConfidenceGauge from './ConfidenceGauge'
import GoogleSignInButton from './GoogleSignInButton'
import {
  IconLightbulb,
  IconGlobe,
  IconCheckCircle,
  IconMessageCircle,
  IconUser,
  IconGauge,
  IconAlertTriangle,
  IconListChecks,
  IconColumns,
  IconDownload,
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

const FEATURES = [
  {
    Icon: IconGauge,
    title: 'Confidence dashboard',
    body: 'See exactly how much of the analysis is backed by real evidence versus inference.',
  },
  {
    Icon: IconAlertTriangle,
    title: 'Contradiction detection',
    body: "Flags where two sections of the report pull in different directions, so you know what to double-check.",
  },
  {
    Icon: IconListChecks,
    title: 'MVP & go-to-market plan',
    body: 'Concrete features to build first, priority channels, and how to land early customers.',
  },
  {
    Icon: IconColumns,
    title: 'Compare ideas side by side',
    body: 'Stack up to five past validations in one table to see which one actually holds up.',
  },
  {
    Icon: IconUser,
    title: 'Your own board',
    body: 'Sign in and every validation you run follows you across devices instead of living in one browser tab.',
  },
  {
    Icon: IconDownload,
    title: 'Shareable reports',
    body: 'Export a PDF or email yourself the full write-up to bring to a co-founder or advisor.',
  },
]

export default function LandingPage({ onStart, currentUser, onSignIn, onSignOut, apiUrl, onAuthenticated }) {
  const { text, settled } = useTypewriter(EXAMPLE_IDEAS)
  const confidence = useCountUp(settled ? 84 : 0, 900)
  const [googleError, setGoogleError] = useState('')

  async function handleGoogleCredential(idToken) {
    setGoogleError('')
    try {
      const res = await fetch(`${apiUrl}/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken }),
      })
      const data = await res.json()
      if (!res.ok) {
        setGoogleError(data.error || 'Google sign-in failed. Please try again.')
        return
      }
      onAuthenticated(data)
    } catch {
      setGoogleError('Could not reach the server. Please try again.')
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-10 sm:pt-14">
        <div className="mb-14 flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-widest text-accent">Affinity</p>
          <div className="flex items-center gap-2">
            {currentUser && (
              <button
                type="button"
                onClick={onSignOut}
                title={`Signed in as ${currentUser.email} - click to sign out`}
                className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
              >
                <IconUser className="h-3 w-3 text-accent" />
                <span className="max-w-[9rem] truncate normal-case">{currentUser.email}</span>
              </button>
            )}
            <span className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-info">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-info" />
              Live
            </span>
          </div>
        </div>

        <section className="fade-in-up mx-auto max-w-xl text-center">
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
            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={onStart}
                className="rounded-full bg-accent px-7 py-3 font-mono text-sm font-semibold uppercase tracking-wide text-white shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-accent-hover"
              >
                Test it out →
              </button>
              {!currentUser && (
                <button
                  type="button"
                  onClick={onSignIn}
                  className="rounded-full border border-border bg-panel px-7 py-3 font-mono text-sm font-semibold uppercase tracking-wide text-text shadow-sm transition-colors hover:border-accent hover:text-accent"
                >
                  Sign in
                </button>
              )}
            </div>
            {!currentUser && apiUrl && onAuthenticated && (
              <div className="mt-1">
                <GoogleSignInButton onCredential={handleGoogleCredential} onError={setGoogleError} />
                {googleError && (
                  <p className="mt-2 max-w-xs text-center text-[11px] text-danger">{googleError}</p>
                )}
              </div>
            )}
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted">
              {currentUser ? 'Signed in · Your validations are saved to your account' : 'No signup required to try · Sign in to save your history'}
            </p>
          </div>
        </section>

        <section
          className="fade-in-up mx-auto mt-14 max-w-2xl rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-7"
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
                  settled ? 'text-info opacity-100' : 'text-muted opacity-0'
                }`}
              >
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-info" />
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
            Everything in one report
          </p>
          <h2
            className="fade-in-up mb-8 text-center font-serif text-2xl text-text"
            style={{ animationDelay: '300ms' }}
          >
            Built for founders who want proof, not vibes.
          </h2>
          <div className="fade-in-up grid gap-x-8 gap-y-6 rounded-2xl border border-border bg-panel p-6 sm:grid-cols-2 sm:p-8 lg:grid-cols-3" style={{ animationDelay: '350ms' }}>
            {FEATURES.map(({ Icon, title, body }) => (
              <div key={title} className="flex gap-3">
                <Icon className="mt-0.5 h-[18px] w-[18px] shrink-0 text-accent" />
                <div>
                  <h3 className="font-serif text-base font-semibold text-text">{title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
                </div>
              </div>
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
            className="rounded-full border border-border px-6 py-2.5 font-mono text-xs uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
          >
            Test it out →
          </button>
          <p className="font-mono text-[11px] uppercase tracking-widest text-muted">
            Free to try · Full report in minutes
          </p>
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
