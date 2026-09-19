// Mirrors backend/agent/structured_output.py's compact_sources(): the
// same default limit (6) and 1-based "src-N" numbering over the raw
// `results` list, so a sourceId a claim cites resolves to the exact
// result the backend actually gave the LLM - see docs/unique-features-plan.md
// §5.1 and graph.py's own comment on this same ordering assumption.
const SOURCE_LIMIT = 6

export function buildSourceMap(results) {
  const map = new Map()
  ;(results || []).slice(0, SOURCE_LIMIT).forEach((result, index) => {
    map.set(`src-${index + 1}`, result)
  })
  return map
}
