import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import GtmCommercialModel from '../GtmCommercialModel'
import MvpDeliveryRoadmap from '../MvpDeliveryRoadmap'

const commercialModel = {
  unitEconomics: {
    estimatedCac: '$120 – $180',
    targetArpu: '$45/month ($540/year)',
    paybackHorizonMonths: '3 – 4 Months',
    ltvToCacRatio: '3.2x',
    economicRationale: 'Low-touch organic acquisition keeps CAC low.',
  },
  pricingTiers: [
    { tierName: 'Starter', price: '$0', billingCycle: 'Free Forever', targetSegment: 'Solo builders', includedFeatures: ['3 active projects'] },
    { tierName: 'Pro', price: '$45', billingCycle: 'per month', targetSegment: 'Growing teams', includedFeatures: ['Unlimited validations'] },
    { tierName: 'Scale', price: '$135', billingCycle: 'per month', targetSegment: 'Agencies', includedFeatures: ['Team seats'] },
  ],
}

const deliveryRoadmap = {
  totalTimelineWeeks: 12,
  teamComposition: [
    { role: 'Full-Stack Engineer', allocation: '1.0 FTE', primaryFocus: 'Pipeline & agent wiring' },
  ],
  phases: [
    { phaseName: 'Phase 1: Proof of Wedge (Alpha)', durationWeeks: 4, coreDeliverables: ['Core workflow'], exitGateMilestones: ['10 active users'] },
    { phaseName: 'Phase 2: Closed Beta Pilot', durationWeeks: 4, coreDeliverables: ['Billing'], exitGateMilestones: ['3 paying pilots'] },
    { phaseName: 'Phase 3: General Availability (GA)', durationWeeks: 4, coreDeliverables: ['Self-serve onboarding'], exitGateMilestones: ['30-day retention >25%'] },
  ],
}

describe('GtmCommercialModel', () => {
  it('renders unit economics stats and the rationale', () => {
    render(<GtmCommercialModel data={commercialModel} />)
    expect(screen.getByText('$120 – $180')).toBeInTheDocument()
    expect(screen.getByText('$45/month ($540/year)')).toBeInTheDocument()
    expect(screen.getByText(/Low-touch organic acquisition/)).toBeInTheDocument()
  })

  it('renders all 3 pricing tiers in order', () => {
    render(<GtmCommercialModel data={commercialModel} />)
    expect(screen.getByText('Starter')).toBeInTheDocument()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Scale')).toBeInTheDocument()
  })

  it('renders nothing when there is no commercial model', () => {
    const { container } = render(<GtmCommercialModel data={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('MvpDeliveryRoadmap', () => {
  it('renders all 3 phases with their deliverables and exit gates', () => {
    render(<MvpDeliveryRoadmap data={deliveryRoadmap} />)
    expect(screen.getByText(/Phase 1: Proof of Wedge/)).toBeInTheDocument()
    expect(screen.getByText(/Phase 2: Closed Beta Pilot/)).toBeInTheDocument()
    expect(screen.getByText(/Phase 3: General Availability/)).toBeInTheDocument()
    expect(screen.getByText('10 active users')).toBeInTheDocument()
  })

  it('renders team sizing with FTE allocations', () => {
    render(<MvpDeliveryRoadmap data={deliveryRoadmap} />)
    expect(screen.getByText('Full-Stack Engineer')).toBeInTheDocument()
    expect(screen.getByText('1.0 FTE')).toBeInTheDocument()
  })

  it('renders nothing when there is no roadmap', () => {
    const { container } = render(<MvpDeliveryRoadmap data={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
