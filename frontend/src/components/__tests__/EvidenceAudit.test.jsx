import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EvidenceAudit, { summarizeAudit } from '../EvidenceAudit'

const swot = { verification: { ran: true, checked: 6, removed: [{ text: 'Unsupported claim', sourceIds: ['src-1'] }] } }
const gtm = { verification: { ran: true, checked: 4, removed: [] } }

describe('EvidenceAudit', () => {
  it('rolls up checked and removed counts across sections that ran', () => {
    const a = summarizeAudit({ swot, gtm, mvp: { verification: { ran: false, checked: 0, removed: [] } } })
    expect(a).toMatchObject({ sectionsChecked: 2, checked: 10, removed: 1 })
  })

  it('renders nothing for older reports with no audit data', () => {
    const { container } = render(<EvidenceAudit swot={{}} gtm={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('states plainly when the check did not run', () => {
    render(<EvidenceAudit mvp={{ verification: { ran: false, checked: 0, removed: [] } }} />)
    expect(screen.getByText(/source check did not run/i)).toBeInTheDocument()
  })

  it('shows what was removed', () => {
    render(<EvidenceAudit swot={swot} gtm={gtm} />)
    expect(screen.getByText(/1 lost their citation/i)).toBeInTheDocument()
  })
})
