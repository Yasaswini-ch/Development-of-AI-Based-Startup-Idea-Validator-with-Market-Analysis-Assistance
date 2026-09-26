// Mirrors backend/agent/structured_output.py's compact_sources(): 1-based
// "src-N" numbering over the raw `results` list, so a sourceId a claim
// cites resolves to the exact result the backend actually gave the LLM -
// see docs/unique-features-plan.md §5.1 and graph.py's own comment on this
// same ordering assumption.
//
// Every result is mapped, not just the first 6: most agents only see
// src-1..src-6, but market_agent.py numbers the whole list and shows up to
// 10 sources picked by angle, so its trends and TAM figures can cite src-7
// or later. Capping here silently dropped those citations.
export function buildSourceMap(results) {
  const map = new Map()
  ;(results || []).forEach((result, index) => {
    map.set(`src-${index + 1}`, result)
  })
  return map
}

// A citation the model wrote inline in prose ("[src-1]", "【src-1】",
// "(src-2, src-5)") instead of in a sourceIds field. The backend strips
// these from marketSize for new runs (extract_inline_citations in
// structured_output.py); this handles reports saved before that.
const INLINE_CITATION = /\s*[[【(（]\s*(src-\d+(?:\s*[,;、]\s*src-\d+)*)\s*[\]】)）]/g

export function extractInlineCitations(text) {
  if (typeof text !== 'string') return { text, sourceIds: [] }
  const sourceIds = []
  for (const match of text.matchAll(INLINE_CITATION)) {
    for (const id of match[1].split(/[\s,;、]+/)) {
      if (id && !sourceIds.includes(id)) sourceIds.push(id)
    }
  }
  const cleaned = text
    .replace(INLINE_CITATION, '')
    .replace(/\s+([.,;:!?])/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .trim()
  return { text: cleaned, sourceIds }
}
