import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import ValidationResults from '../ValidationResults'
import { mockValidation } from '../../mocks/validationMock'

// Regression coverage for the `confidence` naming collision: ValidationResults
// used to declare a local `const confidence = useCountUp(...)` in the same
// scope as the `confidence` prop, which is a SyntaxError (duplicate
// declaration) that broke the whole module. Simply rendering the component
// with a `confidence` prop is enough to catch that regression.
describe('ValidationResults', () => {
  function renderResults(overrides = {}) {
    return render(<ValidationResults {...mockValidation} {...overrides} />)
  }

  it('renders without crashing when given a confidence prop', () => {
    renderResults()
    expect(screen.getByText(/executive summary/i)).toBeInTheDocument()
  })

  it('renders the confidence dashboard from real backend data instead of the old single badge', () => {
    renderResults()
    expect(screen.getByText('Confidence dashboard')).toBeInTheDocument()
    expect(screen.getByText('Source coverage')).toBeInTheDocument()
    // The old summary card badge had its own "Confidence" label sitting
    // next to the count-up percentage; that badge is gone now that the
    // dashboard is the single source of confidence info.
    expect(screen.queryByText('Confidence')).not.toBeInTheDocument()
  })

  it('renders the contradictions banner above the tabs', () => {
    renderResults()
    expect(screen.getByText(/contradictions worth a second look/i)).toBeInTheDocument()
  })

  it('hides the contradictions banner when there are none', () => {
    renderResults({ contradictions: [] })
    expect(screen.queryByText(/contradictions worth a second look/i)).not.toBeInTheDocument()
  })

  it('adds an Experiments & Action Plan tab that renders the mocked experiments and plan', async () => {
    const user = userEvent.setup()
    renderResults()

    await user.click(screen.getByRole('tab', { name: /roadmap/i }))

    expect(screen.getByText(mockValidation.experiments[0].hypothesis)).toBeInTheDocument()
    expect(screen.getByText(/Next 7 days/)).toBeInTheDocument()
  })

  it('passes sourceMap through to Market Opportunity so its claims are citable', async () => {
    const user = userEvent.setup()
    renderResults()

    await user.click(screen.getByRole('tab', { name: /market & rivals/i }))

    // The first market trend cites src-1, so its claim renders a citation marker.
    expect(screen.getByText(mockValidation.marketOpportunity.trends[0].text)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /show source for this claim/i }).length).toBeGreaterThan(0)
  })

  it('labels each tab count with what it counts', () => {
    renderResults()
    expect(screen.getByRole('tab', { name: /evidence/i })).toHaveAttribute('title', `${mockValidation.results.length} sources`)
    expect(screen.getByRole('tab', { name: /build & ship/i })).not.toHaveAttribute('title')
  })
})
