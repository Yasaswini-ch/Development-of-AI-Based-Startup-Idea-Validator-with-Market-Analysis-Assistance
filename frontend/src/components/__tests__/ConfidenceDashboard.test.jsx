import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ConfidenceDashboard from '../ConfidenceDashboard'
import { mockConfidence } from '../../mocks/validationMock'

describe('ConfidenceDashboard', () => {
  it('renders nothing when there is no data', () => {
    const { container } = render(<ConfidenceDashboard data={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a tile per metric with its supporting detail', () => {
    render(<ConfidenceDashboard data={mockConfidence} />)

    expect(screen.getByText('Source coverage')).toBeInTheDocument()
    expect(screen.getByText('3/3 claims cite a source.')).toBeInTheDocument()

    expect(screen.getByText('Cross-source agreement')).toBeInTheDocument()
    expect(screen.getByText('0/3 claims cite 2+ sources.')).toBeInTheDocument()

    expect(screen.getByText('Direct evidence')).toBeInTheDocument()
    expect(screen.getByText('3 direct vs 0 inferred.')).toBeInTheDocument()

    // Average relevance and source recency are two distinct metrics -
    // regression test for a bug where the relevance tile showed the
    // recency detail text instead of its own, and recency had no tile of
    // its own at all.
    expect(screen.getByText('Average relevance')).toBeInTheDocument()
    expect(screen.getByText('How closely cited sources match the search query, on average (0.74 of 1.00).')).toBeInTheDocument()

    expect(screen.getByText('Source recency')).toBeInTheDocument()
    expect(screen.getByText('Median source age: 97 days (3/4 dated).')).toBeInTheDocument()
  })

  it('omits a tile whose metric is missing from the data', () => {
    render(<ConfidenceDashboard data={{ sourceCoverage: mockConfidence.sourceCoverage }} />)
    expect(screen.getByText('Source coverage')).toBeInTheDocument()
    expect(screen.queryByText('Cross-source agreement')).not.toBeInTheDocument()
  })

  it('still shows source recency when there is no average relevance to show alongside it', () => {
    render(<ConfidenceDashboard data={{ sourceRecency: { sourcesWithKnownDate: 0, totalSources: 3, medianAgeDays: null } }} />)
    expect(screen.getByText('Source recency')).toBeInTheDocument()
    expect(screen.getByText('No dated sources available.')).toBeInTheDocument()
    expect(screen.queryByText('Average relevance')).not.toBeInTheDocument()
  })
})
