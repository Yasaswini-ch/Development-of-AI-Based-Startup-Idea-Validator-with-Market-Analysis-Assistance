import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import StatsStrip from '../StatsStrip'

function statValue(label) {
  // CircleStat renders the number and its label as siblings inside one tile.
  const tile = screen.getByText(label).closest('div').parentElement
  return tile.querySelector('span').textContent
}

describe('StatsStrip market gaps tile', () => {
  const results = [{ title: 'a' }, { title: 'b' }]

  it('counts the whiteSpace.opportunities returned by the backend', async () => {
    // Shape produced by backend/agent/white_space.py:analyze_white_space
    const whiteSpace = {
      summary: 's',
      competitionNote: 'n',
      opportunities: [
        { gap: 'one', evidence: 'e', whyNow: 'w' },
        { gap: 'two', evidence: 'e', whyNow: 'w' },
        { gap: 'three', evidence: 'e', whyNow: 'w' },
      ],
    }
    render(<StatsStrip results={results} whiteSpace={whiteSpace} />)
    // CircleStat counts up from 0, so wait for the animation to settle. The
    // count-up runs on requestAnimationFrame, which jsdom slows down when
    // the whole suite runs in parallel, so the timeout is generous.
    await waitFor(() => expect(statValue('Market gaps')).toBe('3'), { timeout: 8000 })
  }, 10000)

  it('shows 0 when white-space analysis is missing', () => {
    render(<StatsStrip results={results} whiteSpace={null} />)
    expect(statValue('Market gaps')).toBe('0')
  })
})
