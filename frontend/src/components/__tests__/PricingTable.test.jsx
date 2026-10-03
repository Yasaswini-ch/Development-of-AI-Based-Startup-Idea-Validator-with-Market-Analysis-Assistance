import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PricingTable, { priceFor } from '../PricingTable'

describe('PricingTable', () => {
  it('prefers stated pricing, marks tiers as estimates, and never invents a price', () => {
    expect(priceFor({ pricing: '$12/mo', estimatedPrice: 'low' })).toEqual({ text: '$12/mo', kind: 'stated' })
    expect(priceFor({ pricing: 'unknown', estimatedPrice: 'mid' })).toEqual({ text: 'Mid-priced', kind: 'estimate' })
    expect(priceFor({ pricing: 'unknown', estimatedPrice: 'unknown' }).kind).toBe('unknown')
  })

  it('links each row to its source and says when no price was found', () => {
    render(
      <PricingTable
        competitors={[
          { name: 'Harvest', pricing: '$12/mo', url: 'https://www.harvestapp.com/pricing', businessModel: 'Subscription' },
          { name: 'Clockify', pricing: 'unknown', estimatedPrice: 'unknown', url: 'https://example.org/x' },
        ]}
      />,
    )
    expect(screen.getByRole('link', { name: 'harvestapp.com' }).getAttribute('href')).toBe('https://www.harvestapp.com/pricing')
    expect(screen.getByText('Not found in sources')).toBeInTheDocument()
  })

  it('renders nothing without competitors', () => {
    const { container } = render(<PricingTable competitors={[]} />)
    expect(container.firstChild).toBeNull()
  })
})
