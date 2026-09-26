// Idea clarity check - runs client-side, before /validate is ever called,
// so a genuinely vague pitch ("an app for pets") doesn't spend a research
// pass and several LLM calls before anyone learns the analysis was thin.
// Deliberately not a hard block: founders can still submit through the
// warning, since a heuristic here can be wrong and the idea is theirs to
// judge, not ours to gatekeep.

// Same generic-noun list IdeaDossier.jsx's keyword extractor already
// treats as too vague to be a "research signal" - reused here so "an app
// for pets" (all generic nouns, no domain-specific term) is recognized
// the same way in both places.
const GENERIC_WORDS = new Set([
  'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
  'with', 'that', 'this', 'it', 'is', 'are', 'was', 'were', 'be', 'been',
  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
  'could', 'should', 'may', 'might', 'can', 'need', 'want', 'use', 'using',
  'used', 'get', 'make', 'help', 'our', 'my', 'your', 'their', 'its', 'we',
  'i', 'you', 'they', 'he', 'she', 'who', 'what', 'how', 'which', 'when',
  'where', 'why', 'not', 'no', 'yes', 'so', 'if', 'as', 'by', 'from',
  'into', 'through', 'about', 'than', 'then', 'also', 'just', 'very',
  'more', 'most', 'some', 'any', 'all', 'each', 'other', 'new', 'app',
  'apps', 'platform', 'solution', 'tool', 'service', 'product', 'based',
  'system', 'startup', 'idea', 'business', 'company',
])

const MIN_WORDS = 8

function specificWords(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 3 && !GENERIC_WORDS.has(w))
}

// Returns { clear: true } or { clear: false, reason } - a short, plain
// explanation of what's missing, meant to sit right under the idea field
// rather than being a generic "please add more detail."
export function assessIdeaClarity(idea) {
  const trimmed = (idea || '').trim()
  const wordCount = trimmed ? trimmed.split(/\s+/).length : 0

  if (wordCount === 0) {
    return { clear: true }
  }
  if (wordCount < MIN_WORDS) {
    return {
      clear: false,
      reason: 'This is quite short — add what the product does or who it helps, so the research agents have something specific to search for.',
    }
  }
  const specific = specificWords(trimmed)
  if (specific.length === 0) {
    return {
      clear: false,
      reason: 'This describes a generic app or tool without saying what it actually does — name the workflow, customer, or problem so the research is grounded rather than guessed.',
    }
  }
  return { clear: true }
}
