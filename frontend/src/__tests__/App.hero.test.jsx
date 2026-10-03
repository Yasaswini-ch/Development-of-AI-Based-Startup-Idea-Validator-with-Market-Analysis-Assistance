import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { SAMPLE_IDEAS } from '../lib/examples'

describe('landing hero and sample ideas', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    global.fetch = vi.fn(() => Promise.reject(new Error('no network in this test')))
  })

  it('shows the tabbed report preview on the landing page', () => {
    render(<App />)
    expect(screen.getByRole('tablist', { name: /sample report sections/i })).toBeInTheDocument()
  })

  it('carries the idea typed in the hero into the form', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Your startup idea'), 'A dog-walking marketplace')
    await user.click(screen.getAllByRole('button', { name: /validate my idea/i })[0])
    expect(screen.getByLabelText(/startup idea/i)).toHaveValue('A dog-walking marketplace')
  })

  it('fills the whole form from a sample chip', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getAllByRole('button', { name: /validate my idea/i })[0])
    await user.click(screen.getByRole('button', { name: 'Freelancer invoicing' }))
    expect(screen.getByLabelText(/target customer/i)).toHaveValue(
      SAMPLE_IDEAS.find((x) => x.label === 'Freelancer invoicing').targetCustomer,
    )
    expect(screen.getByLabelText(/problem being solved/i)).not.toHaveValue('')
  })
})
