import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MarketOpportunity from '../MarketOpportunity'
import ProvenanceBadge from '../ProvenanceBadge'
import VoiceOfMarketSection from '../VoiceOfMarketCard'
import MarketViabilityIndex from '../MarketViabilityIndex'
import { mockMarketOpportunity } from '../../mocks/validationMock'

const sourceMap = new Map([
  ['src-1', { title: 'Report', url: 'https://example.com', snippet: '...' }],
  ['src-3', { title: 'Reddit', url: 'https://reddit.com/r/creators', snippet: '...' }],
])

describe('ProvenanceBadge', () => {
  it('shows Grounded with the source count when sources exist', () => {
    render(<ProvenanceBadge sourceIds={['src-1', 'src-2']} />)
    expect(screen.getByText('Grounded')).toBeInTheDocument()
  })

  it('shows Inferred when there are no sources', () => {
    render(<ProvenanceBadge sourceIds={[]} />)
    expect(screen.getByText('Inferred')).toBeInTheDocument()
  })

  it('reads status directly off a backend-computed provenance object', () => {
    render(<ProvenanceBadge provenance={{ status: 'inferred', sourceCount: 0 }} sourceIds={['src-1']} />)
    expect(screen.getByText('Inferred')).toBeInTheDocument()
  })
})

describe('VoiceOfMarketSection', () => {
  it('renders each quote with its attribution', () => {
    render(<VoiceOfMarketSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    expect(screen.getByText(/juggling three free tools/)).toBeInTheDocument()
    expect(screen.getByText('Reddit thread')).toBeInTheDocument()
  })

  it('renders nothing when there are no quotes', () => {
    const { container } = render(<VoiceOfMarketSection quotes={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the aggregate signal counts above the quote cards', () => {
    render(
      <VoiceOfMarketSection
        quotes={mockMarketOpportunity.voiceOfMarket}
        summary={mockMarketOpportunity.voiceOfMarketSummary}
      />,
    )
    expect(screen.getByText(/6 observed frictions/)).toBeInTheDocument()
    expect(screen.getByText(/found across 12 sources scanned/)).toBeInTheDocument()
  })

  it('renders fine with no summary (older cached data)', () => {
    render(<VoiceOfMarketSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    expect(screen.getByText(/juggling three free tools/)).toBeInTheDocument()
  })
})

describe('MarketViabilityIndex', () => {
  it('renders all 5 dimensions with the composite score', () => {
    render(<MarketViabilityIndex data={mockMarketOpportunity.viabilityIndex} sourceMap={sourceMap} />)
    expect(screen.getByText('Demand Urgency')).toBeInTheDocument()
    expect(screen.getByText('Expansion Velocity')).toBeInTheDocument()
    expect(screen.getByText('Target Accessibility')).toBeInTheDocument()
    expect(screen.getByText('Barrier to Entry / Moat')).toBeInTheDocument()
    expect(screen.getByText('Capital Efficiency')).toBeInTheDocument()
    expect(screen.getByText(/^\d\.\d \/ 5$/)).toBeInTheDocument()
  })

  it('renders nothing when there is no index data', () => {
    const { container } = render(<MarketViabilityIndex data={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('MarketOpportunity with Pillar 1/2 additions', () => {
  it('renders the viability index inline; voice-of-market now lives in the Customers tab', () => {
    render(<MarketOpportunity data={mockMarketOpportunity} sourceMap={sourceMap} />)
    expect(screen.queryByText('Voice of the Market')).not.toBeInTheDocument()
    expect(screen.getByText('Market Viability & Dynamics')).toBeInTheDocument()
  })

  it('still renders fine when voiceOfMarket/viabilityIndex are absent (older cached data)', () => {
    const data = { ...mockMarketOpportunity, voiceOfMarket: undefined, viabilityIndex: undefined }
    render(<MarketOpportunity data={data} sourceMap={sourceMap} />)
    expect(screen.queryByText('Voice of the Market')).not.toBeInTheDocument()
    expect(screen.queryByText('Market Viability & Dynamics')).not.toBeInTheDocument()
  })
})
