import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ThoughtLine from '../ThoughtLine'

describe('ThoughtLine', () => {
  it('shows the working label and the steps reached so far', () => {
    render(<ThoughtLine label="Validating your idea" steps={['Researching the web', 'Scoring viability']} />)
    expect(screen.getByText('Validating your idea')).toBeInTheDocument()
    expect(screen.getByText('Researching the web')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Scoring viability')
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
  })

  it('folds the trace on click', async () => {
    const user = userEvent.setup()
    render(<ThoughtLine steps={['Researching the web']} />)
    await user.click(screen.getByRole('button'))
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')
  })

  it('settles into the done label, folds the trace and reports the time', () => {
    const onSettle = vi.fn()
    const { rerender } = render(<ThoughtLine steps={['Researching the web']} doneLabel="Validated in" onSettle={onSettle} />)
    rerender(<ThoughtLine steps={['Researching the web']} doneLabel="Validated in" onSettle={onSettle} working={false} />)
    expect(screen.getAllByText('Validated in').length).toBeGreaterThan(0)
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')
    expect(onSettle).toHaveBeenCalledTimes(1)
  })
})
