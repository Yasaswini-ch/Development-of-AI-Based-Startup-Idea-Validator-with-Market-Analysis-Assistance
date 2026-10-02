import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuthPanel from '../AuthPanel'

function respond(body, ok = true, status = ok ? 200 : 400) {
  return Promise.resolve({ ok, status, json: async () => body })
}

describe('AuthPanel password reset', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('asks for a reset link and shows the same generic message the server sends', async () => {
    global.fetch.mockImplementation(() => respond({ status: 'ok', message: 'If an account exists for that email, a reset link is on its way.' }, true, 202))
    const user = userEvent.setup()
    render(<AuthPanel apiUrl="http://api" onAuthenticated={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /forgot password/i }))
    expect(screen.getByRole('heading', { name: /reset your password/i })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Email'), 'founder@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(/reset link is on its way/i)
    const [url, init] = global.fetch.mock.calls[0]
    expect(url).toBe('http://api/auth/forgot-password')
    expect(JSON.parse(init.body)).toEqual({ email: 'founder@example.com' })
  })

  it('opens the new-password form when arriving from the emailed link', () => {
    render(<AuthPanel apiUrl="http://api" onAuthenticated={vi.fn()} resetToken="tok-abcdefghijklmnopqrstuvwxyz" />)
    expect(screen.getByRole('heading', { name: /choose a new password/i })).toBeInTheDocument()
    expect(screen.getByLabelText('New password')).toBeInTheDocument()
  })

  it('rejects mismatched passwords without calling the server', async () => {
    const user = userEvent.setup()
    render(<AuthPanel apiUrl="http://api" onAuthenticated={vi.fn()} resetToken="tok-abcdefghijklmnopqrstuvwxyz" />)
    await user.type(screen.getByLabelText('New password'), 'a-brand-new-passphrase')
    await user.type(screen.getByLabelText('Confirm new password'), 'something-different-here')
    await user.click(screen.getByRole('button', { name: /set new password/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/do not match/i)
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('sets the password, then returns to sign in without signing the user in', async () => {
    global.fetch.mockImplementation(() => respond({ status: 'ok' }))
    const onAuthenticated = vi.fn()
    const user = userEvent.setup()
    render(<AuthPanel apiUrl="http://api" onAuthenticated={onAuthenticated} resetToken="tok-abcdefghijklmnopqrstuvwxyz" />)

    await user.type(screen.getByLabelText('New password'), 'a-brand-new-passphrase')
    await user.type(screen.getByLabelText('Confirm new password'), 'a-brand-new-passphrase')
    await user.click(screen.getByRole('button', { name: /set new password/i }))

    await waitFor(() => expect(screen.getByRole('heading', { name: /^sign in$/i })).toBeInTheDocument())
    expect(screen.getByRole('status')).toHaveTextContent(/password updated/i)
    const [url, init] = global.fetch.mock.calls[0]
    expect(url).toBe('http://api/auth/reset-password')
    expect(JSON.parse(init.body)).toEqual({ token: 'tok-abcdefghijklmnopqrstuvwxyz', password: 'a-brand-new-passphrase' })
    expect(onAuthenticated).not.toHaveBeenCalled()
  })

  it('shows the server message for an expired link and offers a new one', async () => {
    global.fetch.mockImplementation(() => respond({ error: 'This reset link is invalid or has expired. Request a new one.' }, false, 400))
    const user = userEvent.setup()
    render(<AuthPanel apiUrl="http://api" onAuthenticated={vi.fn()} resetToken="tok-abcdefghijklmnopqrstuvwxyz" />)

    await user.type(screen.getByLabelText('New password'), 'a-brand-new-passphrase')
    await user.type(screen.getByLabelText('Confirm new password'), 'a-brand-new-passphrase')
    await user.click(screen.getByRole('button', { name: /set new password/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/i)
    await user.click(screen.getByRole('button', { name: /request a new one/i }))
    expect(screen.getByRole('heading', { name: /reset your password/i })).toBeInTheDocument()
  })
})
