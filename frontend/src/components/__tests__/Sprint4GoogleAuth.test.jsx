import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AuthPanel from '../AuthPanel'

vi.mock('../GoogleSignInButton', () => ({
  default: ({ onCredential }) => (
    <button type="button" onClick={() => onCredential('fake-id-token')}>
      Mock Google Sign-In
    </button>
  ),
}))

describe('AuthPanel with Google sign-in', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('still renders the email/password form alongside the Google button', () => {
    render(<AuthPanel apiUrl="http://localhost:8000" onAuthenticated={() => {}} />)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByText('Mock Google Sign-In')).toBeInTheDocument()
  })

  it('posts the credential to /auth/google and calls onAuthenticated with the response', async () => {
    const onAuthenticated = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ token: 'jwt-token', user: { id: 'u1', email: 'a@b.com', authProvider: 'google' } }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<AuthPanel apiUrl="http://localhost:8000" onAuthenticated={onAuthenticated} />)
    await user.click(screen.getByText('Mock Google Sign-In'))

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith({
      token: 'jwt-token',
      user: { id: 'u1', email: 'a@b.com', authProvider: 'google' },
    }))
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/auth/google',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ idToken: 'fake-id-token' }),
      }),
    )
  })

  it('shows the backend error message when Google sign-in fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: 'Google sign-in could not be verified. Please try again.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<AuthPanel apiUrl="http://localhost:8000" onAuthenticated={() => {}} />)
    await user.click(screen.getByText('Mock Google Sign-In'))

    expect(await screen.findByText('Google sign-in could not be verified. Please try again.')).toBeInTheDocument()
  })
})
