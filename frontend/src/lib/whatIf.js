// Client-side mirror of the backend's deterministic scoring, so a founder can
// move the three inputs and see how the headline would change. It must stay in
// step with backend/agent/viability_score.py (calculate_market_viability) and
// backend/agent/verdict.py (build_verdict); the tests pin the arithmetic.
// Only these inputs feed the score - price and CAC do not, so they are not
// offered as sliders.

export const WEIGHTS = { demand: 0.4, risk: 0.3, velocity: 0.3 }
export const PURSUE_AT = 65
export const RETHINK_BELOW = 40
export const MIN_EVIDENCE_FOR_PURSUE = 50

// Python's round() rounds halves to even; match it so the baseline reproduces
// the backend's score exactly.
function roundHalfEven(x) {
  const f = Math.floor(x)
  const d = x - f
  if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1
  return Math.round(x)
}

export function score({ demand, risk, velocity }) {
  const raw = WEIGHTS.demand * demand + WEIGHTS.risk * (100 - risk) + WEIGHTS.velocity * velocity
  return Math.max(0, Math.min(100, roundHalfEven(raw)))
}

// facts: { highRisks, unmitigated, unproven, evidence (percent|null), degraded }
export function decide(scoreValue, facts) {
  const { highRisks = 0, unmitigated = 0, unproven = 0, evidence = null, degraded = false } = facts
  let decision
  if (scoreValue < RETHINK_BELOW || highRisks >= 3) decision = 'rethink'
  else if (scoreValue >= PURSUE_AT && unmitigated === 0 && unproven === 0) decision = 'pursue'
  else decision = 'validate_first'
  if (decision === 'pursue' && evidence !== null && evidence < MIN_EVIDENCE_FOR_PURSUE) decision = 'validate_first'
  if (degraded && decision === 'pursue') decision = 'validate_first'
  return decision
}

export function factsFrom({ swot, assumptions, confidence, marketOpportunity }) {
  const risks = (swot?.risks || []).filter((r) => r && r.severity === 'high')
  const unmitigated = risks.filter((r) => !String(r.mitigation || '').trim())
  const unproven = (assumptions?.assumptions || []).filter((a) => a && a.uncertainty === 'high')
  const cov = confidence?.sourceCoverage
  let evidence = null
  if (cov && typeof cov.percentage === 'number' && cov.totalClaims) evidence = Math.round(cov.percentage)
  else if (typeof confidence?.percentage === 'number') evidence = Math.round(confidence.percentage)
  return {
    highRisks: risks.length,
    unmitigated: unmitigated.length,
    unproven: unproven.length,
    evidence,
    degraded: Boolean(marketOpportunity?.degraded),
  }
}
