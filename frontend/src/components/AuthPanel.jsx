import { useState } from 'react'
import { IconAlertTriangle, IconColumns, IconGauge, IconUser } from './icons'
import GoogleSignInButton from './GoogleSignInButton'
import useAuthRequest from '../hooks/useAuthRequest'

const MIN_PASSWORD_LENGTH = 8

const BENEFITS = [
  { Icon: IconUser, text: 'Every validation you run follows your account, not one browser tab.' },
  { Icon: IconGauge, text: 'Personal analytics across everything you\'ve validated so far.' },
  { Icon: IconColumns, text: 'Compare past ideas side by side from any device.' },
]

// Posts to a reset endpoint. Not useAuthRequest: that hook signs the user in on
// success, and a reset must not (the person still has to sign in with the new
// password).
async function postReset(apiUrl, path, body) {
  const res = await fetch(`${apiUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Something went wrong. Please try again.')
  return data
}

export default function AuthPanel({ apiUrl, onAuthenticated, onBack, resetToken }) {
  // 'login' | 'signup' | 'forgot' (ask for a reset link) | 'reset' (arrived from the emailed link)
  const [mode, setMode] = useState(resetToken ? 'reset' : 'login')
  const [notice, setNotice] = useState('')
  const [confirm, setConfirm] = useState('')
  const [resetBusy, setResetBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  // Only true once Google's button has actually rendered - the "or"
  // divider is hidden otherwise, so a deployment without Google sign-in (or
  // with Google's script blocked) doesn't open the form with a lone "or".
  const [googleReady, setGoogleReady] = useState(false)
  const { submit, isSubmitting, isWaking, error, setError } = useAuthRequest(apiUrl, onAuthenticated)

  async function handleSubmit(event) {
    event.preventDefault()

    if (mode === 'signup' && password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }

    await submit(`/auth/${mode}`, { email, password })
  }

  async function handleForgot(event) {
    event.preventDefault()
    setError('')
    setResetBusy(true)
    try {
      const data = await postReset(apiUrl, '/auth/forgot-password', { email })
      setNotice(data.message || 'If an account exists for that email, a reset link is on its way.')
    } catch (err) {
      setError(err.message)
    } finally {
      setResetBusy(false)
    }
  }

  async function handleReset(event) {
    event.preventDefault()
    setError('')
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    if (password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setResetBusy(true)
    try {
      await postReset(apiUrl, '/auth/reset-password', { token: resetToken, password })
      setPassword('')
      setConfirm('')
      setNotice('Password updated. Sign in with your new password.')
      setMode('login')
    } catch (err) {
      setError(err.message)
    } finally {
      setResetBusy(false)
    }
  }

  function goTo(nextMode) {
    setMode(nextMode)
    setError('')
    setNotice('')
  }

  async function handleGoogleCredential(idToken) {
    await submit('/auth/google', { idToken }, 'Google sign-in failed. Please try again.')
  }

  return (
    <div className="mx-auto grid max-w-3xl gap-10 lg:grid-cols-[1fr,20rem] lg:items-start">
      <div>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Account</p>
            <h2 className="font-serif text-2xl text-text">
              {{ login: 'Sign in', signup: 'Create an account', forgot: 'Reset your password', reset: 'Choose a new password' }[mode]}
            </h2>
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

        {(mode === 'login' || mode === 'signup') && (
        <p className="mb-4 text-sm leading-relaxed text-muted">
          {mode === 'login'
            ? "Sign in to see your own board - validations you run while signed in are saved to your account instead of just this device."
            : `${googleReady ? 'Use your Google account or an email and password' : 'One email and password, nothing else'} - your validations get tied to this account instead of only this device.`}
        </p>
        )}

        {(mode === 'forgot' || mode === 'reset') && (
          <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm">
            {mode === 'forgot' ? (
              <form onSubmit={handleForgot} className="space-y-4">
                <p className="text-sm leading-relaxed text-muted">
                  Enter the email you signed up with and we will send a link to choose a new password. The link works once and
                  expires in 30 minutes.
                </p>
                <div>
                  <label htmlFor="forgot-email" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
                    Email
                  </label>
                  <input
                    id="forgot-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    className="w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-accent"
                  />
                </div>
                {notice && (
                  <p role="status" className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-text">
                    {notice}
                  </p>
                )}
                {error && (
                  <div className="flex items-start gap-2 rounded-lg border border-danger/20 bg-danger/5 p-3 text-sm text-danger" role="alert">
                    <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
                <button
                  type="submit"
                  disabled={resetBusy}
                  className="w-full rounded-full bg-accent px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {resetBusy ? 'One moment…' : 'Send reset link'}
                </button>
                <button
                  type="button"
                  onClick={() => goTo('login')}
                  className="w-full text-center font-mono text-[11px] uppercase tracking-wide text-muted hover:text-accent"
                >
                  Back to sign in
                </button>
              </form>
            ) : (
              <form onSubmit={handleReset} className="space-y-4">
                <div>
                  <label htmlFor="reset-password" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
                    New password
                  </label>
                  <input
                    id="reset-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
                    required
                    minLength={MIN_PASSWORD_LENGTH}
                    className="w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm text-text outline-none placeholder:text-muted focus:border-accent"
                  />
                </div>
                <div>
                  <label htmlFor="reset-confirm" className="mb-1.5 block font-mono text-xs uppercase tracking-wider text-muted">
                    Confirm new password
                  </label>
                  <input
                    id="reset-confirm"
                    type="password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
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
                  disabled={resetBusy}
                  className="w-full rounded-full bg-accent px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {resetBusy ? 'One moment…' : 'Set new password'}
                </button>
                <button
                  type="button"
                  onClick={() => goTo('forgot')}
                  className="w-full text-center font-mono text-[11px] uppercase tracking-wide text-muted hover:text-accent"
                >
                  Link expired? Request a new one
                </button>
              </form>
            )}
          </div>
        )}

        {(mode === 'login' || mode === 'signup') && (
        <div className="rounded-2xl border border-border bg-panel p-6 shadow-sm">
        <GoogleSignInButton onCredential={handleGoogleCredential} onError={setError} onReady={() => setGoogleReady(true)} />
        {googleReady && (
          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">or</span>
            <span className="h-px flex-1 bg-border" />
          </div>
        )}

        <form onSubmit={handleSubmit}>
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
            {mode === 'login' && (
              <button
                type="button"
                onClick={() => goTo('forgot')}
                className="mt-2 font-mono text-[11px] uppercase tracking-wide text-muted hover:text-accent"
              >
                Forgot password?
              </button>
            )}
          </div>

          {notice && (
            <p role="status" className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-text">
              {notice}
            </p>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-danger/20 bg-danger/5 p-3 text-sm text-danger" role="alert">
              <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {isWaking && (
            <p className="text-center font-mono text-[11px] uppercase tracking-wide text-muted">
              Waking up the server, this can take up to a minute…
            </p>
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
              setNotice('')
            }}
            className="w-full text-center font-mono text-[11px] uppercase tracking-wide text-muted hover:text-accent"
          >
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>
        </form>
        </div>
        )}
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
