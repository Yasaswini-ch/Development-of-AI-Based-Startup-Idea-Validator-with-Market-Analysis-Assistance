import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MarketOpportunity from '../MarketOpportunity'
import { buildSourceMap, extractInlineCitations } from '../../lib/sources'

const results = Array.from({ length: 8 }, (_, i) => ({
  title: `Source ${i + 1}`,
  url: `https://example${i + 1}.com/report`,
  snippet: 'snippet',
}))

describe('inline citations', () => {
  it('maps every result, including ones past the first six', () => {
    expect(buildSourceMap(results).get('src-8').title).toBe('Source 8')
  })

  it('pulls 【src-N】 markers out of prose', () => {
    expect(extractInlineCitations('Worth $5.9 billion 【src-1】【src-3】.')).toEqual({
      text: 'Worth $5.9 billion.',
      sourceIds: ['src-1', 'src-3'],
    })
  })

  it('renders market-size markers as citations and grounds the badge', () => {
    const data = {
      marketSize: 'The market was $5.9 billion in 2024 【src-1】【src-8】.',
      trends: [],
      segments: [],
      tam: { text: '$5.9 billion', sourceIds: [] },
    }
    render(<MarketOpportunity data={data} sourceMap={buildSourceMap(results)} />)
    expect(screen.queryByText(/src-1/)).not.toBeInTheDocument()
    expect(screen.getByText(/The market was \$5\.9 billion in 2024\./)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /show source for this claim/i })).toHaveLength(2)
    expect(screen.getByText('Grounded')).toBeInTheDocument()
  })
})
