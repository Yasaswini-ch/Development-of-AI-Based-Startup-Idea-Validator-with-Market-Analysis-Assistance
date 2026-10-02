import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import VerdictWhatIf from '../VerdictWhatIf'

const viability = { score: 58, marketDemand: 60, executionRisk: 40, growthVelocity: 53 } // 24 + 18 + 15.9 -> 58
const verdict = { decision: 'validate_first', label: 'Validate first', score: 58, scoreName: 'Market viability' }

describe('VerdictWhatIf', () => {
  it('starts at the report score and flips the call when inputs improve', () => {
    render(<VerdictWhatIf verdict={verdict} marketViability={viability} swot={{ risks: [] }} assumptions={{ assumptions: [] }} />)
    expect(screen.getByTestId('whatif-score').textContent).toBe('58')
    fireEvent.change(screen.getByLabelText('Market demand'), { target: { value: '90' } })
    expect(Number(screen.getByTestId('whatif-score').textContent)).toBeGreaterThanOrEqual(65)
    expect(screen.getByTestId('whatif-decision').textContent).toMatch(/pursue/i)
  })

  it('needs the open assumptions dealt with before it can say pursue', () => {
    render(<VerdictWhatIf verdict={verdict} marketViability={viability} swot={{ risks: [] }} assumptions={{ assumptions: [{ uncertainty: 'high' }] }} />)
    fireEvent.change(screen.getByLabelText('Market demand'), { target: { value: '100' } })
    expect(screen.getByTestId('whatif-decision').textContent).toMatch(/validate first/i)
    fireEvent.click(screen.getByLabelText(/assume the unmitigated/i))
    expect(screen.getByTestId('whatif-decision').textContent).toMatch(/pursue/i)
  })

  it('renders nothing when the headline is not the viability score', () => {
    const { container } = render(<VerdictWhatIf verdict={{ ...verdict, scoreName: 'Opportunity score' }} marketViability={viability} />)
    expect(container.firstChild).toBeNull()
  })
})
