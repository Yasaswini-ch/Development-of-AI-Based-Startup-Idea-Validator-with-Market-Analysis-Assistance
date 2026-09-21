// Per-device validation history, kept in localStorage. There's no accounts
// system (see CompareIdeas.jsx's own note on this), so this is the only way
// a normal user gets back a session id/link for an older validation without
// having saved the email or URL themselves.

const STORAGE_KEY = 'affinity:history'
const MAX_ENTRIES = 25

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeAll(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // localStorage unavailable (private browsing, storage full, etc.) -
    // history just won't persist; the rest of the app still works.
  }
}

export function getHistory() {
  return readAll().sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
}

// Upserts by sessionId so re-opening or re-comparing an existing entry
// doesn't create a duplicate row.
export function addHistoryEntry({ sessionId, idea, targetCustomer }) {
  if (!sessionId) return
  const entries = readAll().filter((entry) => entry.sessionId !== sessionId)
  entries.unshift({
    sessionId,
    idea: idea || '',
    targetCustomer: targetCustomer || '',
    createdAt: new Date().toISOString(),
  })
  writeAll(entries.slice(0, MAX_ENTRIES))
}

export function removeHistoryEntry(sessionId) {
  writeAll(readAll().filter((entry) => entry.sessionId !== sessionId))
}

export function clearHistory() {
  writeAll([])
}
