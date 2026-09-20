import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ContradictionsBanner from '../ContradictionsBanner'
import { mockContradictions, mockResults } from '../../mocks/validationMock'
import { buildSourceMap } from '../../lib/sources'

describe('ContradictionsBanner', () => {
  it('renders nothing when there are no contradictions', () => {
    const { container } = render(<ContradictionsBanner data={[]} sourceMap={new Map()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when data is not an array (e.g. still loading)', () => {
    const { container } = render(<ContradictionsBanner data={null} sourceMap={new Map()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a flag per contradiction with a resolvable citation', () => {
    const sourceMap = buildSourceMap(mockResults)
    render(<ContradictionsBanner data={mockContradictions} sourceMap={sourceMap} />)

    expect(screen.getByText(/Contradictions worth a second look/i)).toBeInTheDocument()
    expect(screen.getByText(mockContradictions[0].summary)).toBeInTheDocument()
    expect(screen.getByText(mockContradictions[1].summary)).toBeInTheDocument()
    // First contradiction cites 2 sources (src-1, src-3) -> 2 citation markers.
    expect(screen.getAllByRole('button', { name: /show source for this claim/i })).toHaveLength(3)
  })
})
