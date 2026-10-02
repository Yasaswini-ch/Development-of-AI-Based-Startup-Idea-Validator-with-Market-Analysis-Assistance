import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AgentsGrid from '../AgentsGrid'
import { AGENTS } from '../agentsData'

describe('AgentsGrid', () => {
  it('lists every agent with a unique name and a valid kind', () => {
    expect(new Set(AGENTS.map((a) => a.name)).size).toBe(AGENTS.length)
    for (const a of AGENTS) expect(['ai', 'rules']).toContain(a.kind)
  })

  it('shows the real counts in its heading and summary', () => {
    render(<AgentsGrid />)
    const ai = AGENTS.filter((a) => a.kind === 'ai').length
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(`${AGENTS.length} agents and engines`)
    expect(screen.getByText(new RegExp(`${ai} AI agents reason`))).toBeInTheDocument()
  })

  it('filters to AI agents or rule-based engines', () => {
    render(<AgentsGrid />)
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(AGENTS.length)

    fireEvent.click(screen.getByRole('button', { name: 'Rule-based' }))
    const rules = AGENTS.filter((a) => a.kind === 'rules')
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(rules.length)
    expect(screen.queryByRole('heading', { name: 'SWOT and risk' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'AI agents' }))
    const grid = screen.getByRole('heading', { name: 'SWOT and risk' }).closest('div')
    expect(within(grid).getByText('AI agent')).toBeInTheDocument()
  })
})
