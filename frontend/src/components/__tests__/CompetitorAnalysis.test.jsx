import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CompetitorAnalysis from '../CompetitorAnalysis'

const base = (name, extra = {}) => ({
  name,
  offering: `${name} does things.`,
  url: 'https://publisher.example/best-apps',
  gap: 'x',
  estimatedPrice: 'unknown',
  featureBreadth: 'unknown',
  classification: 'unknown',
  ...extra,
})

describe('CompetitorAnalysis cards', () => {
  it('groups rivals by direct, indirect and other, with counts', () => {
    const data = {
      competitors: [
        base('Clockify', { classification: 'direct' }),
        base('Harvest', { classification: 'direct' }),
        base('PayPal', { classification: 'indirect' }),
        base('TimeLive'),
      ],
    }
    render(<CompetitorAnalysis data={data} />)
    expect(screen.getByRole('heading', { name: 'Direct rivals (2)' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Indirect alternatives (1)' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Other mentions (1)' })).toBeInTheDocument()
  })

  it('keeps a flat list, with no group headings, when nothing is labelled', () => {
    render(<CompetitorAnalysis data={{ competitors: [base('A'), base('B')] }} />)
    expect(screen.queryByRole('heading', { name: /Direct rivals|Indirect alternatives|Other mentions/ })).not.toBeInTheDocument()
  })

  it('shows no provenance tags on the card', () => {
    const data = { competitors: [base('Clockify', { enrichment: { source: 'wikidata', description: 'time tracker' } })] }
    render(<CompetitorAnalysis data={data} />)
    expect(screen.queryByText(/auto-identified|analyzed|wikidata|product hunt/i)).not.toBeInTheDocument()
  })

  it('shows rating, review count and price for an App Store match, plus its icon', () => {
    const data = {
      competitors: [
        base('Notion', {
          enrichment: { source: 'itunes', averageRating: 4.77, ratingCount: 90253, price: 'Free', artworkUrl: 'https://img.example/icon.png' },
        }),
      ],
    }
    const { container } = render(<CompetitorAnalysis data={data} />)
    expect(screen.getByText('★ 4.8 · 90.3K ratings · Free')).toBeInTheDocument()
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://img.example/icon.png')
  })

  it('shows a description and founding year for a Wikidata match, with an initial instead of an image', () => {
    const data = {
      competitors: [
        base('HelloFresh', { enrichment: { source: 'wikidata', description: 'german meal-kit provider', foundedYear: 2011 } }),
      ],
    }
    const { container } = render(<CompetitorAnalysis data={data} />)
    expect(screen.getByText('German meal-kit provider · Founded 2011')).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('H')).toBeInTheDocument()
  })

  it('never uses the publisher article\'s favicon as the competitor logo', () => {
    const { container } = render(<CompetitorAnalysis data={{ competitors: [base('Clockify')] }} />)
    expect(container.querySelector('img')).toBeNull()
  })
})
