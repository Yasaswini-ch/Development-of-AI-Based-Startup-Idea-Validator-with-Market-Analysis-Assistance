import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MarketOpportunity from '../MarketOpportunity'
import { mockMarketOpportunity } from '../../mocks/validationMock'

const sourceMap = new Map([['src-1', { title: 'Report', url: 'https://example.com', snippet: '...' }]])

describe('MarketOpportunity', () => {
  it('renders TAM/SAM/SOM tiers when the backend provides them', () => {
    const data = {
      ...mockMarketOpportunity,
      tam: { text: 'USD 2.4B total addressable market.', sourceIds: ['src-1'] },
      sam: { text: 'USD 800M serviceable via direct-to-creator channels.', sourceIds: [] },
      som: { text: 'USD 40M obtainable in year one.', sourceIds: [] },
    }
    render(<MarketOpportunity data={data} sourceMap={sourceMap} />)

    expect(screen.getByText('TAM')).toBeInTheDocument()
    expect(screen.getByText('USD 2.4B total addressable market.')).toBeInTheDocument()
    expect(screen.getByText('SAM')).toBeInTheDocument()
    expect(screen.getByText('USD 800M serviceable via direct-to-creator channels.')).toBeInTheDocument()
    expect(screen.getByText('SOM')).toBeInTheDocument()
    expect(screen.getByText('USD 40M obtainable in year one.')).toBeInTheDocument()
  })

  it('labels an estimated SAM/SOM as an estimate with its assumption, and never as sourced', () => {
    const data = {
      ...mockMarketOpportunity,
      tam: { text: 'USD 2.4B total addressable market.', sourceIds: ['src-1'] },
      sam: { text: 'About USD 480M (estimate)', sourceIds: [], estimated: true, assumptions: 'Assumes 20% of the TAM is reachable.' },
      som: { text: 'About USD 10M (estimate)', sourceIds: [], estimated: true, assumptions: 'Assumes 2% of the SAM is winnable.' },
    }
    render(<MarketOpportunity data={data} sourceMap={sourceMap} />)

    expect(screen.getAllByText('Estimate')).toHaveLength(2)
    expect(screen.getByText(/Assumes 20% of the TAM is reachable\./)).toBeInTheDocument()
    expect(screen.getAllByText(/Not from a source\./)).toHaveLength(2)
    // The sourced TAM is not marked as an estimate.
    expect(screen.getByText('USD 2.4B total addressable market.').closest('div')).not.toHaveTextContent('Estimate')
  })

  it('omits the tier section entirely when none of TAM/SAM/SOM are supported by sources', () => {
    const data = { ...mockMarketOpportunity, tam: null, sam: null, som: null }
    render(<MarketOpportunity data={data} sourceMap={sourceMap} />)
    expect(screen.queryByText('TAM')).not.toBeInTheDocument()
    expect(screen.queryByText('SAM')).not.toBeInTheDocument()
    expect(screen.queryByText('SOM')).not.toBeInTheDocument()
  })

  it('shows only the tiers that are actually supported, not all three', () => {
    const data = { ...mockMarketOpportunity, tam: { text: 'USD 2.4B market.', sourceIds: [] }, sam: null, som: null }
    render(<MarketOpportunity data={data} sourceMap={sourceMap} />)
    expect(screen.getByText('TAM')).toBeInTheDocument()
    expect(screen.queryByText('SAM')).not.toBeInTheDocument()
    expect(screen.queryByText('SOM')).not.toBeInTheDocument()
  })
})
