import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AnalyticsDashboard from '../AnalyticsDashboard'

const USER_ANALYTICS_FIXTURE = {
  ideasValidated: 2,
  kpis: {
    ideasValidated: 2,
    avgOpportunityScore: 70,
    bestScore: 80,
    bestScoreIdea: 'B2B Invoicing SaaS',
    highRiskAssumptions: 3,
    completeRuns: 1,
    degradedRuns: 1,
    avgSourceAgreement: 74,
  },
  scoreTrend: [
    { idea: 'B2B Invoicing SaaS', createdAt: 1, score: 80, confidencePercentage: 86 },
    { idea: 'Meal Planning App', createdAt: 2, score: 60, confidencePercentage: 71 },
  ],
  scoreByIdea: [
    { idea: 'B2B Invoicing SaaS', score: 80 },
    { idea: 'Meal Planning App', score: 60 },
  ],
  assumptionRiskByCategory: { demand: { high: 2, medium: 1, low: 0 } },
  viabilityDimensions: { marketDemand: 70, executionRisk: 30, growthVelocity: 60, competitionClarity: 80, timing: 50 },
  revenueModelDistribution: [{ model: 'Subscription / SaaS', count: 2, percentage: 100 }],
  swotThemes: { strengths: [{ text: 'Growing market', count: 2 }], risks: [{ text: 'Thin margins', count: 1 }] },
  ideas: [
    {
      sessionId: 's1',
      idea: 'B2B Invoicing SaaS',
      targetCustomer: 'SMB finance teams',
      problem: 'Manual invoicing eats hours per week',
      createdAt: 1,
      score: 80,
      marketSize: 'USD 4.2B growing',
      topRisk: 'Market education cost',
      risks: [{ risk: 'Market education cost', severity: 'high' }],
      assumptions: [{ assumption: 'SMBs will pay $29/mo', uncertainty: 'high', howToValidate: 'Interview 10 SMBs' }],
      revenueModels: [{ name: 'SaaS Subscription', rationale: 'Recurring, predictable revenue' }],
      nextSteps: ['Interview 10 SMB finance managers'],
      competitionLabel: 'Low',
      confidencePercentage: 86,
      recommendation: 'Strong candidate - pursue now.',
      status: 'Complete',
    },
    {
      sessionId: 's2',
      idea: 'Meal Planning App',
      targetCustomer: 'Busy families',
      problem: 'Weekly meal planning takes too long',
      createdAt: 2,
      score: 60,
      marketSize: 'USD 6.1B growing',
      topRisk: 'High competition',
      risks: [{ risk: 'High competition', severity: 'high' }],
      assumptions: [],
      revenueModels: [{ name: 'Freemium', rationale: 'Standard for this category' }],
      nextSteps: [],
      competitionLabel: 'High',
      confidencePercentage: 71,
      recommendation: 'Moderate - needs sharper positioning.',
      status: 'Degraded',
    },
  ],
}

async function renderSignedIn() {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => USER_ANALYTICS_FIXTURE })
  render(<AnalyticsDashboard apiUrl="http://api" token="tok" />)
  await waitFor(() => expect(screen.getAllByText('B2B Invoicing SaaS').length).toBeGreaterThan(0))
}

describe('AnalyticsDashboard', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the device-local empty state when signed out with no history', () => {
    render(<AnalyticsDashboard apiUrl="http://api" token={null} />)
    expect(screen.getByText(/No validations yet on this device/)).toBeInTheDocument()
  })

  it('fetches and renders the Overview tab by default when signed in', async () => {
    await renderSignedIn()

    expect(global.fetch).toHaveBeenCalledWith('http://api/me/analytics', expect.objectContaining({ headers: { Authorization: 'Bearer tok' } }))
    expect(screen.getAllByText('2').length).toBeGreaterThan(0) // ideas validated KPI
    expect(screen.getByText('70')).toBeInTheDocument() // avg opportunity score
  })

  it('shows an empty state for a signed-in user with zero validations', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...USER_ANALYTICS_FIXTURE, ideasValidated: 0 }) })

    render(<AnalyticsDashboard apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText(/No validations yet on this account/)).toBeInTheDocument())
  })

  it('shows an error state when the analytics request fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false })

    render(<AnalyticsDashboard apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText(/Couldn't load your analytics/)).toBeInTheDocument())
  })

  it('switches to the Comparison Matrix tab and shows every idea with its recommendation', async () => {
    await renderSignedIn()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Comparison matrix' }))

    expect(screen.getByText('Strong candidate - pursue now.')).toBeInTheDocument()
    expect(screen.getByText('Moderate - needs sharper positioning.')).toBeInTheDocument()
    expect(screen.getByText('SaaS Subscription')).toBeInTheDocument()
  })

  it('switches to Validation History and expands a card to show its detail', async () => {
    await renderSignedIn()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Validation history' }))

    // First card defaults open.
    expect(screen.getByText('Interview 10 SMB finance managers')).toBeInTheDocument()
    expect(screen.getByText(/Interview 10 SMBs/)).toBeInTheDocument()

    // Second card starts collapsed - its next steps aren't rendered yet.
    expect(screen.queryByText('Freemium', { exact: false })).not.toBeInTheDocument()
    await user.click(screen.getByText('Meal Planning App'))
    expect(screen.getByText('Freemium', { exact: false })).toBeInTheDocument()
  })

  it('switches to Score Trends and renders both trend charts', async () => {
    await renderSignedIn()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Score trends' }))

    expect(screen.getByText('Score over time')).toBeInTheDocument()
    expect(screen.getByText('Source agreement trend')).toBeInTheDocument()
  })
})
