import { describe, expect, it } from 'vitest'
import { decide, factsFrom, score } from './whatIf'

describe('what-if scoring mirrors the backend', () => {
  it('matches 0.4*demand + 0.3*(100-risk) + 0.3*velocity', () => {
    expect(score({ demand: 80, risk: 20, velocity: 70 })).toBe(77) // 32 + 24 + 21
    expect(score({ demand: 0, risk: 100, velocity: 0 })).toBe(0)
    expect(score({ demand: 100, risk: 0, velocity: 100 })).toBe(100)
  })

  it('rounds halves to even like Python', () => {
    expect(score({ demand: 50, risk: 50, velocity: 55 })).toBe(52) // 51.5 -> 52
    expect(score({ demand: 50, risk: 50, velocity: 45 })).toBe(48) // 48.5 -> 48
  })

  it('applies the verdict rules', () => {
    expect(decide(39, {})).toBe('rethink')
    expect(decide(70, { highRisks: 3 })).toBe('rethink')
    expect(decide(70, {})).toBe('pursue')
    expect(decide(70, { unproven: 1 })).toBe('validate_first')
    expect(decide(70, { evidence: 40 })).toBe('validate_first')
    expect(decide(70, { degraded: true })).toBe('validate_first')
    expect(decide(64, {})).toBe('validate_first')
  })

  it('reads the facts from the report', () => {
    const f = factsFrom({
      swot: { risks: [{ severity: 'high', mitigation: '' }, { severity: 'high', mitigation: 'x' }, { severity: 'low' }] },
      assumptions: { assumptions: [{ uncertainty: 'high' }, { uncertainty: 'low' }] },
      confidence: { sourceCoverage: { percentage: 61.6, totalClaims: 10 } },
      marketOpportunity: { degraded: false },
    })
    expect(f).toEqual({ highRisks: 2, unmitigated: 1, unproven: 1, evidence: 62, degraded: false })
  })
})
