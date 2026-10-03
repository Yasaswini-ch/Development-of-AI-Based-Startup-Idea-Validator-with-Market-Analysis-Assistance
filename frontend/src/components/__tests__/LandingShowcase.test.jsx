import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PipelineShowcase, { STEPS } from '../PipelineShowcase'
import PlayableVerdict from '../PlayableVerdict'
import ReceiptsStrip from '../ReceiptsStrip'

describe('landing showcase', () => {
  it('lists the 17 real pipeline steps and tags only the certain ones', () => {
    render(<PipelineShowcase />)
    expect(STEPS).toHaveLength(17)
    expect(screen.getAllByRole('listitem')).toHaveLength(17)
    expect(screen.getByText('Verdict')).toBeInTheDocument()
  })

  it('moves the playable verdict with the sliders', () => {
    render(<PlayableVerdict />)
    expect(screen.getByTestId('playable-decision').textContent).toMatch(/validate first/i)
    fireEvent.change(screen.getByLabelText('Market demand'), { target: { value: '100' } })
    fireEvent.change(screen.getByLabelText('Execution risk'), { target: { value: '0' } })
    expect(Number(screen.getByTestId('playable-score').textContent)).toBeGreaterThanOrEqual(65)
    expect(screen.getByTestId('playable-decision').textContent).toMatch(/pursue/i)
    fireEvent.change(screen.getByLabelText('Market demand'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Growth velocity'), { target: { value: '0' } })
    expect(screen.getByTestId('playable-decision').textContent).toMatch(/rethink/i)
  })

  it('states what the product cannot do', () => {
    render(<ReceiptsStrip />)
    expect(screen.getByText(/What it cannot do/)).toBeInTheDocument()
  })
})
