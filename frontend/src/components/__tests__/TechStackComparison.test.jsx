import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ComparisonTable, { ROWS } from '../ComparisonTable'
import TechStack, { STACK } from '../TechStack'
import AgentsGrid from '../AgentsGrid'
import { AGENTS } from '../agentsData'

describe('TechStack', () => {
  it('names the PDF and email tools the backend really uses', () => {
    render(<TechStack />)
    expect(screen.getByText('ReportLab')).toBeInTheDocument()
    expect(screen.getByText('SendGrid')).toBeInTheDocument()
    expect(STACK.every((g) => g.items.length > 0)).toBe(true)
  })
})

describe('ComparisonTable', () => {
  it('renders one row per aspect with both columns', () => {
    render(<ComparisonTable />)
    expect(screen.getAllByRole('row')).toHaveLength(ROWS.length + 1)
    expect(screen.getByRole('columnheader', { name: 'Affinity' })).toBeInTheDocument()
  })
})

describe('agent tool tags', () => {
  it('gives every agent at least one tool tag', () => {
    expect(AGENTS.every((a) => a.tools?.length > 0)).toBe(true)
    render(<AgentsGrid />)
    expect(screen.getByLabelText('Competitor discovery tools')).toHaveTextContent('spaCy NER')
  })
})
