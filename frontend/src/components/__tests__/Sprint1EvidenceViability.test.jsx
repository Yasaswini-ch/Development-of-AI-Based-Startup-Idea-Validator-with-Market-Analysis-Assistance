import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import MarketOpportunity from '../MarketOpportunity'
import ProvenanceBadge from '../ProvenanceBadge'
import VoiceOfMarketSection, { VoiceOfCustomerSection, VoiceOfOwnerSection } from '../VoiceOfMarketCard'
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

describe('VoiceOfCustomerSection', () => {
  it('renders each quote with its attribution', () => {
    render(<VoiceOfCustomerSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    expect(screen.getByText(/juggling three free tools/)).toBeInTheDocument()
    expect(screen.getAllByText('Reddit thread').length).toBeGreaterThan(0)
  })

  it('renders nothing when there are no quotes', () => {
    const { container } = render(<VoiceOfCustomerSection quotes={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the aggregate signal counts above the quote cards', () => {
    render(
      <VoiceOfCustomerSection
        quotes={mockMarketOpportunity.voiceOfMarket}
        summary={mockMarketOpportunity.voiceOfMarketSummary}
      />,
    )
    expect(screen.getByText(/6 observed frictions/)).toBeInTheDocument()
    expect(screen.getByText(/found across 12 sources scanned/)).toBeInTheDocument()
  })

  it('renders fine with no summary (older cached data)', () => {
    render(<VoiceOfCustomerSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    expect(screen.getByText(/juggling three free tools/)).toBeInTheDocument()
  })

  it('groups cards under a theme heading when more than one theme is present', () => {
    render(<VoiceOfCustomerSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    expect(screen.getByText(/Pricing & Cost/)).toBeInTheDocument()
    expect(screen.getByText(/Integrations & Compatibility/)).toBeInTheDocument()
  })

  it('shows every quote at once, with nothing hidden behind a toggle', () => {
    render(<VoiceOfCustomerSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    // All 5 fixture quotes should be visible simultaneously - no "show more".
    expect(screen.getByText(/juggling three free tools/)).toBeInTheDocument()
    expect(screen.getByText(/growing fast and adoption/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /show.*more/i })).not.toBeInTheDocument()
  })

  it('filters to just one dimension via the filter tabs', async () => {
    const user = userEvent.setup()
    render(<VoiceOfCustomerSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    await user.click(screen.getByRole('tab', { name: 'Structural Tailwind' }))
    expect(screen.getByText(/growing fast and adoption/)).toBeInTheDocument()
    expect(screen.queryByText(/juggling three free tools/)).not.toBeInTheDocument()
  })
})

describe('VoiceOfOwnerSection', () => {
  it('renders owner-side quotes under owner-specific dimension labels', () => {
    render(<VoiceOfOwnerSection quotes={mockMarketOpportunity.voiceOfOwner} summary={mockMarketOpportunity.voiceOfOwnerSummary} />)
    expect(screen.getByText('Voice of the Owner')).toBeInTheDocument()
    expect(screen.getByText(/hard to hire good engineers/)).toBeInTheDocument()
    expect(screen.getAllByText('Operational Friction').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Growth & Traction').length).toBeGreaterThan(0)
  })

  it('renders nothing when there are no owner quotes', () => {
    const { container } = render(<VoiceOfOwnerSection quotes={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('VoiceOfMarketSection (combined)', () => {
  it('renders both the customer and owner voice blocks', () => {
    render(
      <VoiceOfMarketSection
        quotes={mockMarketOpportunity.voiceOfMarket}
        summary={mockMarketOpportunity.voiceOfMarketSummary}
        ownerQuotes={mockMarketOpportunity.voiceOfOwner}
        ownerSummary={mockMarketOpportunity.voiceOfOwnerSummary}
      />,
    )
    expect(screen.getByText('Voice of the Customer')).toBeInTheDocument()
    expect(screen.getByText('Voice of the Owner')).toBeInTheDocument()
  })

  it('renders nothing when both customer and owner quotes are empty', () => {
    const { container } = render(<VoiceOfMarketSection quotes={[]} ownerQuotes={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders just the customer block when there is no owner data (older cached reports)', () => {
    render(<VoiceOfMarketSection quotes={mockMarketOpportunity.voiceOfMarket} />)
    expect(screen.getByText('Voice of the Customer')).toBeInTheDocument()
    expect(screen.queryByText('Voice of the Owner')).not.toBeInTheDocument()
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
    expect(screen.queryByText('Voice of the Customer')).not.toBeInTheDocument()
    expect(screen.getByText('Market Viability & Dynamics')).toBeInTheDocument()
  })

  it('still renders fine when voiceOfMarket/viabilityIndex are absent (older cached data)', () => {
    const data = { ...mockMarketOpportunity, voiceOfMarket: undefined, viabilityIndex: undefined }
    render(<MarketOpportunity data={data} sourceMap={sourceMap} />)
    expect(screen.queryByText('Voice of the Customer')).not.toBeInTheDocument()
    expect(screen.queryByText('Market Viability & Dynamics')).not.toBeInTheDocument()
  })
})
