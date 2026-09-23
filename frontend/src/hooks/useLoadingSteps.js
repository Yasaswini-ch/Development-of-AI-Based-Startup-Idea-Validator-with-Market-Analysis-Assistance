import { useEffect, useState } from 'react'

// Grouped to match the real LangGraph pipeline (backend/agent/graph.py) -
// web_search+confidence_indicator, market_opportunity+competitor_discovery+
// opportunity_score+white_space, viability_score, mvp_recommendation+
// gtm_strategy, contradiction_detector+experiment_generator+action_plan,
// confidence_dashboard - collapsed into user-facing phases rather than
// naming all 14 nodes individually.
export const LOADING_PHASES = [
  'Researching the web',
  'Sizing market & competitors',
  'Scoring viability',
  'Building your MVP & GTM plan',
  'Checking for contradictions',
  'Finalizing your report',
]

export default function useLoadingSteps(isActive, intervalMs = 2200) {
  const [stepIndex, setStepIndex] = useState(0)

  useEffect(() => {
    if (!isActive) {
      setStepIndex(0)
      return
    }
    const id = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, LOADING_PHASES.length - 1))
    }, intervalMs)
    return () => clearInterval(id)
  }, [isActive, intervalMs])

  return { phases: LOADING_PHASES, currentIndex: stepIndex }
}
