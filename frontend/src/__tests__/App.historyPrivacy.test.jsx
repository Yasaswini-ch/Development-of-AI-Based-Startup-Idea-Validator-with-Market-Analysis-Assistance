import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { getHistory } from '../lib/history'
import { addToCompareList, getCompareList } from '../lib/compareList'

// Regression coverage for a reported privacy bug: lib/history.js and
// lib/compareList.js are kept in localStorage, which is shared by every
// account that ever signs in on the same browser (a shared/lab computer,
// for instance) - not scoped to a person or session. A prior signed-in
// account's validations (idea + target customer text) stayed in those
// lists and showed up in the next person's History/Compare screens the
// moment they signed in, even though the account itself was different.
describe('device-local history/compare lists do not leak across accounts', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('clears the device-local history and compare lists on sign-in', async () => {
    // Simulate a previous, unrelated visitor's leftovers sitting in this
    // browser's localStorage before the next person ever opens the app.
    localStorage.setItem(
      'affinity:history',
      JSON.stringify([{ sessionId: 'prev-session', idea: 'A previous, unrelated idea', createdAt: new Date().toISOString() }]),
    )
    addToCompareList('prev-session')
    expect(getHistory()).toHaveLength(1)
    expect(getCompareList()).toEqual(['prev-session'])

    global.fetch = vi.fn((url) => {
      if (String(url).endsWith('/auth/login')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ token: 'tok-456', user: { id: 'user-2', email: 'next-person@example.com' } }),
        })
      }
      if (String(url).endsWith('/auth/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ id: 'user-2', email: 'next-person@example.com' }),
        })
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`))
    })

    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await user.type(screen.getByLabelText('Email'), 'next-person@example.com')
    await user.type(screen.getByLabelText('Password'), 'a-different-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(getHistory()).toHaveLength(0))
    expect(getCompareList()).toEqual([])
  })
})
