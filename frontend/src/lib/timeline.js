// One week axis for every plan in the report. The Delivery Roadmap
// (backend/agent/delivery_roadmap.py) is the single build timeline; the GTM
// launch phases and the validation action plan are labelled against the
// same "Weeks a–b" scale instead of each inventing its own units.

export function weekLabel(start, end) {
  if (!end || end <= start) return `Week ${start}`
  return `Weeks ${start}–${end}`
}

// [{ start, end, label }] per roadmap phase, cumulative from week 1.
export function roadmapWeekRanges(roadmap) {
  const phases = Array.isArray(roadmap?.phases) ? roadmap.phases : []
  let cursor = 1
  return phases.map((phase) => {
    const weeks = Math.max(1, Math.round(Number(phase.durationWeeks) || 1))
    const range = { start: cursor, end: cursor + weeks - 1 }
    cursor += weeks
    return { ...range, label: weekLabel(range.start, range.end) }
  })
}

// The action plan's next7Days / next30Days / next90Days windows on the same
// axis: week 1, weeks 2-4, weeks 5-13.
export const ACTION_PLAN_WEEKS = {
  '7d': weekLabel(1),
  '30d': weekLabel(2, 4),
  '90d': weekLabel(5, 13),
}
