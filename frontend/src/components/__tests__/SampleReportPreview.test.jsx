import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import SampleReportPreview, { TABS } from '../SampleReportPreview'

describe('SampleReportPreview', () => {
  it('is labelled as a sample and shows all eight tabs', () => {
    render(<SampleReportPreview />)
    expect(screen.getByText('Sample')).toBeInTheDocument()
    expect(screen.getAllByRole('tab')).toHaveLength(TABS.length)
    expect(TABS).toHaveLength(8)
  })

  it('switches the panel when a tab is clicked', () => {
    render(<SampleReportPreview />)
    expect(screen.getByRole('tabpanel')).toHaveTextContent('18 sources')
    fireEvent.click(screen.getByRole('tab', { name: 'Competitors' }))
    expect(screen.getByRole('tabpanel')).toHaveTextContent('6 rivals found')
  })

  it('moves between tabs with the arrow keys', () => {
    render(<SampleReportPreview />)
    fireEvent.keyDown(screen.getByRole('tablist'), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Market' })).toHaveAttribute('aria-selected', 'true')
  })
})
