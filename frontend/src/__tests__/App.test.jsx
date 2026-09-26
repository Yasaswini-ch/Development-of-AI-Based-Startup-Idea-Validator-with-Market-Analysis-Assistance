import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

// Regression coverage for a bug where isAdmin (and anything else GET
// /auth/me adds beyond the bare {id, email} that /auth/login and
// /auth/signup return) never showed up after signing in through the UI -
// only a full page reload happened to trigger the effect that fetches it.
describe('App sign-in flow', () => {
  beforeEach(() => {
    localStorage.clear()
    global.fetch = vi.fn((url) => {
      if (String(url).endsWith('/auth/login')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ token: 'tok-123', user: { id: 'user-1', email: 'admin@example.com' } }),
        })
      }
      if (String(url).endsWith('/auth/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ id: 'user-1', email: 'admin@example.com', isAdmin: true }),
        })
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`))
    })
  })

  it('shows Platform health after signing in, without a page reload, once /auth/me confirms isAdmin', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await user.type(screen.getByLabelText('Email'), 'admin@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    // The login response alone has no isAdmin field - only the follow-up
    // GET /auth/me call does, so the menu item only appears once that
    // second fetch has resolved and updated currentUser.
    await user.click(await screen.findByTitle('Signed in as admin@example.com'))
    expect(await screen.findByText('Platform health')).toBeInTheDocument()
  })
})

// Regression coverage for preserving a validation run anonymously, then
// signed into right after - without this, it stayed stuck in this browser's
// device-local history since sessions are only tagged with a user_id at
// creation time (see agent/session_store.claim_session).
describe('App sign-in claims an in-progress guest validation', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.setItem(
      'affinity:lastValidation',
      JSON.stringify({
        validation: { sessionId: 'guest-session-42', summary: 'A plant swap app' },
        lastSubmission: { idea: 'A plant swap app', targetCustomer: '', problem: '' },
        updatedAt: null,
      }),
    )
  })

  it('POSTs the guest sessionId to /me/claim-session once sign-in succeeds', async () => {
    const claimCalls = []
    global.fetch = vi.fn((url, options) => {
      if (String(url).endsWith('/auth/login')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ token: 'tok-123', user: { id: 'user-1', email: 'founder@example.com' } }),
        })
      }
      if (String(url).endsWith('/auth/me')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ id: 'user-1', email: 'founder@example.com' }) })
      }
      if (String(url).endsWith('/me/claim-session')) {
        claimCalls.push(options)
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ claimed: true }) })
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`))
    })

    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await user.type(screen.getByLabelText('Email'), 'founder@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(claimCalls).toHaveLength(1))
    expect(JSON.parse(claimCalls[0].body)).toEqual({ sessionId: 'guest-session-42' })
    expect(claimCalls[0].headers.Authorization).toBe('Bearer tok-123')
  })
})
