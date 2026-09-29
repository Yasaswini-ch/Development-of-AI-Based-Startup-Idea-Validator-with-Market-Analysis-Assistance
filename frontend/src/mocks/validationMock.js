// Local fixture for developing/testing the frontend without a running
// backend. Shapes here mirror the real /validate response contracts:
// - confidence / contradictions: already produced by the pipeline
//   (backend/agent/graph.py's confidence_dashboard_node and
//   contradiction_detector_node) and returned by POST /validate today.
// - experiments / actionPlan: Tracks C/D (docs/unique-features-plan.md
//   §5.4-5.5) haven't landed in the backend yet, so this is the only
//   source for them until then. Swap this fixture for the live response
//   field once agent/experiment_generator.py and agent/action_plan.py ship
//   - no component prop changes needed, the shapes already match.

export const mockResults = [
  {
    title: 'The Creator Economy Market Report 2026',
    url: 'https://example.com/creator-economy-2026',
    snippet: 'The creator tooling market is growing at 24% CAGR, driven by demand for lightweight monetization tools.',
    angle: 'Market size & trends',
    score: 0.86,
    publishedAt: '2026-06-02T00:00:00Z',
  },
  {
    title: 'Why most creator SaaS tools fail to retain users',
    url: 'https://example.com/creator-saas-churn',
    snippet: 'Churn analysis across 40 creator tools shows onboarding friction as the top cause of week-1 drop-off.',
    angle: 'Industry news',
    score: 0.71,
    publishedAt: '2026-03-15T00:00:00Z',
  },
  {
    title: 'Budget-conscious creators are price-sensitive on subscriptions',
    url: 'https://example.com/creator-pricing-survey',
    snippet: 'A survey of 500 part-time creators found 62% would not pay more than $10/month for a new tool.',
    angle: 'Customer demand',
    score: 0.64,
    publishedAt: '2025-11-20T00:00:00Z',
  },
  {
    title: 'Competitor landscape: link-in-bio and tipping tools',
    url: 'https://example.com/link-in-bio-competitors',
    snippet: 'Overview of established players and their pricing tiers in the link-in-bio space.',
    angle: 'Competitors',
    score: 0.58,
  },
]

export const mockMarketOpportunity = {
  marketSize: 'The creator monetization tooling market is estimated at $2.4B and growing quickly as more part-time creators look for income.',
  opportunityScore: 62,
  tam: { text: 'USD 2.4B - the full creator monetization tooling market.', sourceIds: ['src-1'] },
  sam: { text: 'USD 600M - part-time creators reachable through direct-to-creator channels.', sourceIds: ['src-2'] },
  som: null,
  trends: [
    { text: 'The creator tooling market is growing at roughly 24% CAGR.', sourceIds: ['src-1'] },
    { text: 'Onboarding friction is the leading cause of early churn across creator SaaS tools.', sourceIds: ['src-2'] },
  ],
  segments: [
    {
      segment: 'Part-time hobbyist creators',
      painPoints: 'Juggling multiple free tools with no unified way to collect payments.',
      motivations: 'Want a simple way to earn a small side income from their audience.',
      buyingBehavior: 'Reads as price-resistant - most are unwilling to pay more than $10/month.',
      sourceIds: ['src-3'],
    },
  ],
  voiceOfMarket: [
    {
      quote: 'I keep juggling three free tools just to collect a few tips from my audience.',
      speakerOrSource: 'Reddit thread',
      sourceId: 'src-3',
      url: 'https://reddit.com/r/creators/comments/example',
      sentiment: 'negative_towards_incumbent',
      taggedDimension: 'Observed Friction',
    },
  ],
  voiceOfMarketSummary: {
    dimensionCounts: { 'Observed Friction': 6, 'Demand Signal': 2, 'Structural Tailwind': 1 },
    sourcesScanned: 12,
    sourcesWithSignal: 9,
  },
  viabilityIndex: {
    compositeScore: 68,
    dimensions: [
      {
        name: 'Demand Urgency',
        score: 4,
        rating: 'High',
        rationale: 'Pain points about payment collection recur across sources.',
        sourceIds: ['src-3'],
        provenance: { status: 'grounded', sourceCount: 1 },
      },
      {
        name: 'Expansion Velocity',
        score: 4,
        rating: 'High',
        rationale: 'Trend signals describe a market growing at roughly 24% CAGR.',
        sourceIds: ['src-1'],
        provenance: { status: 'grounded', sourceCount: 1 },
      },
      {
        name: 'Target Accessibility',
        score: 3,
        rating: 'Medium',
        rationale: 'One of one segment(s) have a known buying behavior.',
        sourceIds: ['src-3'],
        provenance: { status: 'grounded', sourceCount: 1 },
      },
      {
        name: 'Barrier to Entry / Moat',
        score: 3,
        rating: 'Medium',
        rationale: 'No direct competitors were found; that may be a real gap or thin search coverage.',
        sourceIds: [],
        provenance: { status: 'inferred', sourceCount: 0 },
      },
      {
        name: 'Capital Efficiency',
        score: 4,
        rating: 'High',
        rationale: 'Software-only delivery keeps initial infrastructure cost low.',
        sourceIds: [],
        provenance: { status: 'inferred', sourceCount: 0 },
      },
    ],
  },
}

export const mockConfidence = {
  agreeingSources: 3,
  totalSources: 4,
  percentage: 75,
  label: '3/4 sources agree',
  perAngle: {
    'Market size & trends': { agreeingSources: 1, totalSources: 1, percentage: 100, label: '1/1 sources agree' },
    'Industry news': { agreeingSources: 1, totalSources: 1, percentage: 100, label: '1/1 sources agree' },
    'Customer demand': { agreeingSources: 1, totalSources: 1, percentage: 100, label: '1/1 sources agree' },
    Competitors: { agreeingSources: 0, totalSources: 1, percentage: 0, label: '0/1 sources agree' },
  },
  sourceCoverage: { claimsWithSource: 3, totalClaims: 3, percentage: 100 },
  crossSourceAgreement: { claimsWithMultipleSources: 0, totalClaims: 3, percentage: 0 },
  directEvidenceRatio: { direct: 3, inferred: 0, percentage: 100 },
  averageRelevance: 0.74,
  sourceRecency: { sourcesWithKnownDate: 3, totalSources: 4, medianAgeDays: 97 },
}

export const mockContradictions = [
  {
    type: 'marketGrowthVsWeakDemand',
    summary:
      'The market is described as growing, but demand evidence for "Part-time hobbyist creators" reads as weak or unproven - the two claims pull in different directions.',
    sourceIds: ['src-1', 'src-3'],
  },
  {
    type: 'premiumPositioningVsPriceSensitiveSegment',
    summary:
      'GTM positioning leans premium, but the target segment\'s buying behavior reads as price-sensitive.',
    sourceIds: ['src-3'],
  },
]

export const mockExperiments = [
  {
    hypothesis: 'Part-time creators will pay for a unified tipping + subscription tool.',
    method: 'Run a landing-page smoke test with a waitlist and a mock pricing page.',
    successMetric: 'At least 8% of qualified visitors join the waitlist.',
    duration: '7 days',
    budget: 'low',
    relatedRiskIds: ['risk-1'],
  },
  {
    hypothesis: 'Reducing onboarding to under 3 steps meaningfully improves week-1 retention.',
    method: 'Ship a stripped-down onboarding flow to a 10% cohort and compare week-1 retention.',
    successMetric: 'Week-1 retention improves by at least 15% relative to control.',
    duration: '30 days',
    budget: 'medium',
    relatedRiskIds: ['risk-2'],
  },
]

export const mockActionPlan = {
  next7Days: {
    title: 'Test the highest-risk assumptions',
    items: [
      { text: 'Launch the landing-page smoke test for willingness to pay.' },
      { text: 'Interview 5 part-time creators about current tipping/subscription setup.' },
    ],
  },
  next30Days: {
    title: 'Build and measure the smallest useful MVP',
    items: [
      { text: 'Ship a single-page tipping link with Stripe Connect payouts.' },
      { text: 'Instrument onboarding funnel and measure week-1 retention.' },
    ],
  },
  next90Days: {
    title: 'Execute the strongest evidence-backed GTM channel',
    items: [
      { text: 'Run a creator-referral program on the channel with the highest signal.' },
    ],
  },
}

export const mockValidation = {
  summary:
    'A creator monetization tool shows real market growth, but price-sensitivity in the core segment is a risk worth testing before building further.',
  results: mockResults,
  marketOpportunity: mockMarketOpportunity,
  competitors: { competitors: [] },
  whiteSpace: null,
  swot: {
    strengths: [{ text: 'Low-friction setup compared to existing tools.', sourceIds: ['src-2'] }],
    weaknesses: [{ text: 'No differentiated payments infrastructure yet.', sourceIds: [] }],
    opportunities: [{ text: 'Growing demand for creator monetization tools.', sourceIds: ['src-1'] }],
    threats: [{ text: 'Established link-in-bio tools already bundle tipping.', sourceIds: ['src-4'] }],
    risks: [
      { risk: 'Target segment may not convert to paid.', severity: 'high', likelihood: 'medium', sourceIds: ['src-3'] },
      { risk: 'Onboarding drop-off mirrors competitor churn patterns.', severity: 'medium', likelihood: 'medium', sourceIds: ['src-2'] },
    ],
  },
  mvp: {
    features: [
      { feature: 'Single-page tipping link with instant payouts', effort: 'low', sourceIds: ['src-4'] },
      { feature: 'One-click subscription tier', effort: 'medium', sourceIds: [] },
    ],
  },
  gtm: {
    positioning: 'Position as the fastest way for a part-time creator to start earning, not a premium creator suite.',
    positioningSourceIds: ['src-3'],
    channels: [{ channel: 'Creator referral partnerships', sourceIds: ['src-2'] }],
    earlyCustomerApproach: 'Recruit first 50 creators from niche subreddits and Discord communities.',
    earlyCustomerApproachSourceIds: ['src-2'],
  },
  confidence: mockConfidence,
  contradictions: mockContradictions,
  experiments: mockExperiments,
  actionPlan: mockActionPlan,
  errors: {},
  sessionId: 'mock-session',
}
