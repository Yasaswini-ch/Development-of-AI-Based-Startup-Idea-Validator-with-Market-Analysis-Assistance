import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import StrategicWedgeSection from '../StrategicWedgeCard'
import WhiteSpaceAnalysis from '../WhiteSpaceAnalysis'

const blueprints = [
  {
    opportunityTitle: 'A focused wedge for Freelance collectives',
    convictionPercent: 80,
    vectors: {
      observedFriction: 'They lose hours reconciling multi-client payouts.',
      incumbentBlindspot: 'Acme: Charges per seat; No multi-party splits',
      structuralTailwind: 'The market is growing at 20% CAGR.',
      asymmetricWedge: 'Lead with what this segment already wants: instant splits.',
      defensibilityMoat: 'Only 1 named competitor(s) were found.',
    },
    keyRisk: 'Execution speed, not the wedge itself, is the main risk here.',
    supportingSourceIds: ['src-1'],
  },
]

describe('StrategicWedgeSection', () => {
  it('renders the opportunity title and conviction badge collapsed', () => {
    render(<StrategicWedgeSection blueprints={blueprints} />)
    expect(screen.getByText('A focused wedge for Freelance collectives')).toBeInTheDocument()
    expect(screen.getByText('80% conviction')).toBeInTheDocument()
    expect(screen.queryByText(/reconciling multi-client payouts/)).not.toBeInTheDocument()
  })

  it('expands to show all 5 vectors and the key risk on click', async () => {
    const user = userEvent.setup()
    render(<StrategicWedgeSection blueprints={blueprints} />)
    await user.click(screen.getByRole('button', { name: /focused wedge for Freelance collectives/ }))

    expect(screen.getByText('Observed Friction')).toBeInTheDocument()
    expect(screen.getByText('Incumbent Blindspot')).toBeInTheDocument()
    expect(screen.getByText('Structural Tailwind')).toBeInTheDocument()
    expect(screen.getByText('Asymmetric Wedge')).toBeInTheDocument()
    expect(screen.getByText('Defensibility Moat')).toBeInTheDocument()
    expect(screen.getByText(/Execution speed, not the wedge itself/)).toBeInTheDocument()
  })

  it('renders nothing when there are no blueprints', () => {
    const { container } = render(<StrategicWedgeSection blueprints={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('WhiteSpaceAnalysis with strategic wedge blueprints', () => {
  it('renders the wedge section alongside the existing opportunity cards', () => {
    const data = {
      opportunities: [{ title: 'Serve freelancers', why: 'pain', fit: 'fit', evidence: 'ev' }],
      blueprints,
    }
    render(<WhiteSpaceAnalysis data={data} />)
    expect(screen.getByText('Serve freelancers')).toBeInTheDocument()
    expect(screen.getByText('Strategic Wedge Blueprints')).toBeInTheDocument()
  })

  it('still renders fine when blueprints are absent (older cached data)', () => {
    const data = { opportunities: [{ title: 'Serve freelancers', why: 'pain', fit: 'fit', evidence: 'ev' }] }
    render(<WhiteSpaceAnalysis data={data} />)
    expect(screen.queryByText('Strategic Wedge Blueprints')).not.toBeInTheDocument()
  })
})
