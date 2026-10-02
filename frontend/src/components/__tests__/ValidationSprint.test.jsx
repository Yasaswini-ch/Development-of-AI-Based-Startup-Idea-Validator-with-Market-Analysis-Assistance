import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import ValidationSprint from '../ValidationSprint'

const plan = {
  sprint: {
    note: 'Built from this report.',
    weeks: [
      { week: 1, title: 'Test', tasks: [{ task: 'Paid beta', confirmsIf: '10% pay', killsIf: 'Nobody pays' }] },
      { week: 2, title: 'Talk', tasks: [{ task: 'Run interviews', confirmsIf: '3 recognise it', killsIf: 'None do' }] },
    ],
  },
  interviewScript: {
    audience: 'Freelancers',
    rules: ['Ask about the past'],
    opening: ['Tell me about the last time'],
    probes: [{ assumption: 'They pay', ask: 'What do you use today?', listenFor: 'Real spend', redFlag: 'No cost' }],
    closing: ['Who else should I talk to?'],
  },
}

describe('ValidationSprint', () => {
  beforeEach(() => localStorage.clear())

  it('renders nothing for older reports without a sprint or script', () => {
    const { container } = render(<ValidationSprint plan={{ next7Days: {} }} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows pass and fail thresholds and counts ticked tasks', () => {
    render(<ValidationSprint plan={plan} />)
    expect(screen.getByText(/Pass: 10% pay/)).toBeInTheDocument()
    expect(screen.getByText(/Fail: Nobody pays/)).toBeInTheDocument()
    expect(screen.getByTestId('sprint-progress').textContent).toMatch(/0 of 2/)
    fireEvent.click(screen.getByLabelText('Paid beta'))
    expect(screen.getByTestId('sprint-progress').textContent).toMatch(/1 of 2/)
  })

  it('remembers ticks across a remount', () => {
    const { unmount } = render(<ValidationSprint plan={plan} />)
    fireEvent.click(screen.getByLabelText('Paid beta'))
    unmount()
    render(<ValidationSprint plan={plan} />)
    expect(screen.getByTestId('sprint-progress').textContent).toMatch(/1 of 2/)
  })

  it('shows the interview script with what to listen for', () => {
    render(<ValidationSprint plan={plan} />)
    expect(screen.getByText('What do you use today?')).toBeInTheDocument()
    expect(screen.getByText(/Listen for: Real spend/)).toBeInTheDocument()
  })
})
