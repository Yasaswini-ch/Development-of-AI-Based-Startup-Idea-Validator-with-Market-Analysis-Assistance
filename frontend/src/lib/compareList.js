// A small persistent "add to compare" basket, kept in localStorage - lets
// HistoryPanel's "Add to compare" button build up a set of session ids
// across several clicks (even across page views) instead of the old
// one-at-a-time "copy link, switch tabs, paste" flow, where copying a
// second link overwrote the first before it could be pasted.

const STORAGE_KEY = 'affinity:compareList'
const MAX_ENTRIES = 5

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : []
  } catch {
    return []
  }
}

function writeAll(ids) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // localStorage unavailable - the basket just won't persist.
  }
}

export function getCompareList() {
  return readAll()
}

export function isInCompareList(sessionId) {
  return readAll().includes(sessionId)
}

export function addToCompareList(sessionId) {
  if (!sessionId) return
  const ids = readAll().filter((id) => id !== sessionId)
  ids.push(sessionId)
  writeAll(ids.slice(-MAX_ENTRIES))
}

export function removeFromCompareList(sessionId) {
  writeAll(readAll().filter((id) => id !== sessionId))
}

export function clearCompareList() {
  writeAll([])
}
