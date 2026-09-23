import { useState } from 'react'
import { IconAlertTriangle, IconColumns, IconGauge, IconUser } from './icons'

const MIN_PASSWORD_LENGTH = 8

const BENEFITS = [
  { Icon: IconUser, text: 'Every validation you run follows your account, not one browser tab.' },
  { Icon: IconGauge, text: 'Personal analytics across everything you\'ve validated so far.' },
  { Icon: IconColumns, text: 'Compare past ideas side by side from any device.' },
]

export default function AuthPanel({ apiUrl, onAuthenticated, onBack }) {
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')

    if (mode === 'signup' && password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }

    setIsSubmitting(true)
    try {
      const res = await fetch(`${apiUrl}/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Something went wrong. Please try again.')
        return
      }
      onAuthenticated(data)
    } catch {
      setError('Could not reach the server. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto grid max-w-3xl gap-10 lg:grid-cols-[1fr,20rem] lg:items-start">
      <div>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Account</p>
            <h2 className="font-serif text-2xl text-text">{mode === 'login' ? 'Sign in' : 'Create an account'}</h2>
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
          {mode === 'login'
            ? "Sign in to see your own board - validations you run while signed in are saved to your account instead of just this device."
            : 'One email and password, nothing else - your validations get tied to this account instead of only this device.'}
        </p>

        <form onSubmit={handleSubmit} className="rounded-2xl border border-border bg-panel p-6 shadow-sm">
        <div className="space-y-4">
          <div>
            <label htmlFor="auth-email" className="mb-1.5 flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted">
              <IconUser className="h-3.5 w-3.5 text-accent" />
              Email
            </label>
            <input
              id="auth-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-accent"
            />
          </div>

          <div>
            <label htmlFor="auth-password" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? `At least ${MIN_PASSWORD_LENGTH} characters` : '••••••••'}
              required
              minLength={mode === 'signup' ? MIN_PASSWORD_LENGTH : undefined}
              className="w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-accent"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-danger/20 bg-danger/5 p-3 text-sm text-danger" role="alert">
              <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-full bg-accent px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>

          <button
            type="button"
            onClick={() => {
              setMode((m) => (m === 'login' ? 'signup' : 'login'))
              setError('')
            }}
            className="w-full text-center font-mono text-[11px] uppercase tracking-wide text-muted hover:text-accent"
          >
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>
        </form>
      </div>

      <div className="hidden lg:block">
        <p className="mb-4 font-mono text-xs uppercase tracking-widest text-muted">Why sign in</p>
        <ul className="space-y-4">
          {BENEFITS.map(({ Icon, text }) => (
            <li key={text} className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                <Icon className="h-4 w-4" />
              </span>
              <p className="text-sm leading-relaxed text-muted">{text}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
