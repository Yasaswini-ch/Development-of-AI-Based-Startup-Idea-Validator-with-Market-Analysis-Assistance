import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ExperimentsActionPlan from '../ExperimentsActionPlan'
import { mockActionPlan, mockExperiments } from '../../mocks/validationMock'

describe('ExperimentsActionPlan', () => {
  it('shows the unavailable state when neither experiments nor a plan exist', () => {
    render(<ExperimentsActionPlan experiments={undefined} actionPlan={undefined} />)
    expect(screen.getByText(/aren.t available yet/i)).toBeInTheDocument()
  })

  it('surfaces the backend error message in the unavailable state when given one', () => {
    render(<ExperimentsActionPlan experiments={[]} actionPlan={null} error="agent timed out" />)
    expect(screen.getByText('agent timed out')).toBeInTheDocument()
  })

  it('renders experiment cards and the 7/30/90-day plan columns', () => {
    render(<ExperimentsActionPlan experiments={mockExperiments} actionPlan={mockActionPlan} />)

    expect(screen.getByText(mockExperiments[0].hypothesis)).toBeInTheDocument()
    expect(screen.getByText(mockExperiments[1].hypothesis)).toBeInTheDocument()
    expect(screen.getByText('Budget: low')).toBeInTheDocument()
    expect(screen.getByText('Budget: medium')).toBeInTheDocument()

    expect(screen.getByText(/Next 7 days/)).toBeInTheDocument()
    expect(screen.getByText(mockActionPlan.next7Days.title)).toBeInTheDocument()
    expect(screen.getByText(/Next 30 days/)).toBeInTheDocument()
    expect(screen.getByText(/Next 90 days/)).toBeInTheDocument()
  })
})
