import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlatformHealth from '../PlatformHealth'

const PLATFORM_METRICS_FIXTURE = {
  windowDays: 30,
  kpis: {
    totalValidations: 847,
    cacheHitRate: 61,
    apiSuccessRate: 94,
    deepAnalysisRate: 8,
    avgLatencySeconds: 3.4,
    activeUsersThisWeek: 127,
  },
  dailyVolume: [{ date: '2026-09-23', count: 40 }, { date: '2026-09-24', count: 44 }],
  cacheEfficiency: [{ date: '2026-09-23', hits: 20, count: 40, hitRate: 33.3 }],
  nodeSuccessRates: { web_search: 98.7, swot: 91.2 },
  modelUsage: [{ model: 'groq/qwen/qwen3.8-27b', count: 62, percentage: 62 }],
  latencyByNode: { swot: 8.2, web_search: 0.3 },
  topCategories: [{ category: 'SaaS / B2B Tools', count: 187 }],
  recentErrors: [
    { timestamp: '2026-09-24T14:32:00Z', node: 'swot', errorType: 'NeedsDeepAnalysisError', modelChain: 'groq/qwen/qwen3.8-27b → groq/openai/gpt-oss-20b', outcome: 'Deep analysis fallback' },
  ],
  emailDelivery: { attempted: 75, sent: 71, deliveryRate: 94.7, failed: 4 },
  tokenUsage: {
    totalTokens: 1_520_000,
    promptTokens: 1_200_000,
    completionTokens: 320_000,
    estimatedCostUsd: 0.54,
    avgTokensPerValidation: 7600,
    avgCostPerValidationUsd: 0.0027,
    tokensTrackedCalls: 200,
    totalCalls: 212,
    daily: [
      { date: '2026-09-23', promptTokens: 600_000, completionTokens: 160_000, totalTokens: 760_000, costUsd: 0.27 },
      { date: '2026-09-24', promptTokens: 600_000, completionTokens: 160_000, totalTokens: 760_000, costUsd: 0.27 },
    ],
    byModel: [{ model: 'groq/qwen/qwen3.8-27b', calls: 200, tokens: 1_520_000, costUsd: 0.54 }],
  },
}

describe('PlatformHealth', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches and renders platform metrics for an admin', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => PLATFORM_METRICS_FIXTURE })

    render(<PlatformHealth apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText('847')).toBeInTheDocument())

    expect(global.fetch).toHaveBeenCalledWith('http://api/admin/platform-metrics?days=30', expect.objectContaining({ headers: { Authorization: 'Bearer tok' } }))
    expect(screen.getByText('61%')).toBeInTheDocument()
    expect(screen.getByText('NeedsDeepAnalysisError')).toBeInTheDocument()
  })

  it('renders token and estimated cost totals', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => PLATFORM_METRICS_FIXTURE })

    render(<PlatformHealth apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText('1.5M')).toBeInTheDocument())
    expect(screen.getByText('Daily token usage')).toBeInTheDocument()
    expect(screen.getByText('$0.0027')).toBeInTheDocument()
    expect(screen.getByText(/12 older calls/)).toBeInTheDocument()
  })

  it('shows a forbidden state on a 403', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 403 })

    render(<PlatformHealth apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText('Admin access required.')).toBeInTheDocument())
  })

  it('shows a generic error state on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 })

    render(<PlatformHealth apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText(/Couldn't load platform metrics/)).toBeInTheDocument())
  })

  it('shows a no-errors message when the error log is empty', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...PLATFORM_METRICS_FIXTURE, recentErrors: [] }) })

    render(<PlatformHealth apiUrl="http://api" token="tok" />)

    await waitFor(() => expect(screen.getByText('No errors recorded in this window.')).toBeInTheDocument())
  })
})
