import {
  IconAlertTriangle,
  IconCheckCircle,
  IconColumns,
  IconFlag,
  IconFlask,
  IconGauge,
  IconGlobe,
  IconListChecks,
  IconMessageCircle,
  IconNewspaper,
  IconShield,
  IconSparkles,
  IconTrendingUp,
} from './icons'

// Every agent and engine in the pipeline (backend/agent/graph.py plus the
// advisor chat graph). `kind: 'ai'` means a language model reasons over the
// evidence; `kind: 'rules'` means plain code scores or checks it with no
// model call - keep that distinction accurate, it's the point of the section.
export const AGENTS = [
  { name: 'Web research', kind: 'rules', Icon: IconGlobe, body: 'Searches five angles across Tavily and DuckDuckGo, then filters duplicates and low-signal sites.' },
  { name: 'Market opportunity', kind: 'ai', Icon: IconTrendingUp, body: 'Sizes the market, spots trends and builds customer segments with pain points and buying behaviour.' },
  { name: 'Competitor discovery', kind: 'ai', Icon: IconColumns, body: 'Finds rivals in the sources, labels them direct or indirect and compares them with your idea.' },
  { name: 'SWOT and risk', kind: 'ai', Icon: IconShield, body: 'Strengths, weaknesses, opportunities, threats and a risk register, each claim tagged Grounded or Inferred.' },
  { name: 'MVP planner', kind: 'ai', Icon: IconListChecks, body: 'Prioritises what to build first from the evidence, and what can wait.' },
  { name: 'Go-to-market', kind: 'ai', Icon: IconFlag, body: 'Positioning, channels and the first-customer approach, grounded in the market data.' },
  { name: 'Assumption tracker', kind: 'ai', Icon: IconFlask, body: 'Surfaces the riskiest hidden assumptions and how to test each one.' },
  { name: 'Revenue models', kind: 'ai', Icon: IconGauge, body: 'Suggests monetisation models that fit this market and customer.' },
  { name: 'Grounding verifier', kind: 'ai', Icon: IconCheckCircle, body: 'Checks that each claim is really supported by the sources it cites.' },
  { name: 'Advisor', kind: 'ai', Icon: IconMessageCircle, body: 'Answers follow-up questions from your report, and searches again only when it needs fresh data.' },
  { name: 'Opportunity score', kind: 'rules', Icon: IconGauge, body: 'A 0 to 100 score from market size and growth signals found in the sources.' },
  { name: 'White-space analyzer', kind: 'rules', Icon: IconSparkles, body: 'Triangulates customer pain against competitor gaps to find openings and an entry wedge.' },
  { name: 'Viability index', kind: 'rules', Icon: IconTrendingUp, body: 'Five dynamics, from demand urgency to capital efficiency, combined into one score.' },
  { name: 'Voice of the market', kind: 'rules', Icon: IconNewspaper, body: 'Pulls verbatim customer quotes from the sources and ties each to where it came from.' },
  { name: 'Confidence dashboard', kind: 'rules', Icon: IconShield, body: 'Scores source coverage, cross-source agreement, direct evidence and relevance.' },
  { name: 'Contradiction detector', kind: 'rules', Icon: IconAlertTriangle, body: 'Flags places where sections of the report disagree with each other.' },
  { name: 'Experiments and action plan', kind: 'rules', Icon: IconFlask, body: 'Turns your top risks into experiments and a 7, 30 and 90 day plan.' },
  { name: 'Verdict', kind: 'rules', Icon: IconCheckCircle, body: 'Pursue, validate first or rethink, with the reasons that decided it.' },
]
