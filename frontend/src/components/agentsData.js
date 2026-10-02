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
  { name: 'Web research', kind: 'rules', Icon: IconGlobe, body: 'Searches five angles across Tavily and DuckDuckGo, then filters duplicates and low-signal sites.', tools: ['Tavily', 'DuckDuckGo'] },
  { name: 'Market opportunity', kind: 'ai', Icon: IconTrendingUp, body: 'Sizes the market, spots trends and builds customer segments with pain points and buying behaviour.', tools: ['CrewAI', 'Groq / Gemini via LiteLLM'] },
  { name: 'Competitor discovery', kind: 'ai', Icon: IconColumns, body: 'Finds rivals in the sources, labels them direct or indirect and compares them with your idea.', tools: ['spaCy NER', 'CrewAI', 'Product Hunt', 'iTunes', 'Wikidata'] },
  { name: 'SWOT and risk', kind: 'ai', Icon: IconShield, body: 'Strengths, weaknesses, opportunities, threats and a risk register, each claim tagged Grounded or Inferred.', tools: ['CrewAI', 'Groq / Gemini via LiteLLM'] },
  { name: 'MVP planner', kind: 'ai', Icon: IconListChecks, body: 'Prioritises what to build first from the evidence, and what can wait.', tools: ['CrewAI', 'LangGraph parallel branch'] },
  { name: 'Go-to-market', kind: 'ai', Icon: IconFlag, body: 'Positioning, channels and the first-customer approach, grounded in the market data.', tools: ['CrewAI', 'LangGraph parallel branch'] },
  { name: 'Assumption tracker', kind: 'ai', Icon: IconFlask, body: 'Surfaces the riskiest hidden assumptions and how to test each one.', tools: ['CrewAI'] },
  { name: 'Revenue models', kind: 'ai', Icon: IconGauge, body: 'Suggests monetisation models that fit this market and customer.', tools: ['CrewAI'] },
  { name: 'Grounding verifier', kind: 'ai', Icon: IconCheckCircle, body: 'Checks that each claim is really supported by the sources it cites.', tools: ['Source-id checks', 'CrewAI'] },
  { name: 'Advisor', kind: 'ai', Icon: IconMessageCircle, body: 'Answers follow-up questions from your report, and searches again only when it needs fresh data.', tools: ['LangGraph chat', 'Gemini', 'Tavily on demand'] },
  { name: 'Opportunity score', kind: 'rules', Icon: IconGauge, body: 'A 0 to 100 score from market size and growth signals found in the sources.', tools: ['Python rules', 'Regex over sources'] },
  { name: 'White-space analyzer', kind: 'rules', Icon: IconSparkles, body: 'Triangulates customer pain against competitor gaps to find openings and an entry wedge.', tools: ['Python rules'] },
  { name: 'Viability index', kind: 'rules', Icon: IconTrendingUp, body: 'Five dynamics, from demand urgency to capital efficiency, combined into one score.', tools: ['Python rules'] },
  { name: 'Voice of the market', kind: 'rules', Icon: IconNewspaper, body: 'Pulls verbatim customer quotes from the sources and ties each to where it came from.', tools: ['Python rules', 'Quote extraction'] },
  { name: 'Confidence dashboard', kind: 'rules', Icon: IconShield, body: 'Scores source coverage, cross-source agreement, direct evidence and relevance.', tools: ['Python rules'] },
  { name: 'Contradiction detector', kind: 'rules', Icon: IconAlertTriangle, body: 'Flags places where sections of the report disagree with each other.', tools: ['Python rules'] },
  { name: 'Experiments and action plan', kind: 'rules', Icon: IconFlask, body: 'Turns your top risks into experiments and a 7, 30 and 90 day plan.', tools: ['Python rules'] },
  { name: 'Verdict', kind: 'rules', Icon: IconCheckCircle, body: 'Pursue, validate first or rethink, with the reasons that decided it.', tools: ['Python rules'] },
]
