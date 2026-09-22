// Client-side half of the JWT auth in backend/agent/auth.py. The token is a
// long-lived (30 day) bearer token, not a session cookie - kept in
// localStorage (survives tab close, unlike sessionStorage) so "my board"
// persists across visits the way an actual account should, at the cost of
// being readable by any script on the page (the usual XSS tradeoff of
// token-in-localStorage vs. an httpOnly cookie - accepted here since this
// app has no other user-generated content that could carry a script
// injection into this origin).

const TOKEN_KEY = 'affinity:token'
const USER_KEY = 'affinity:user'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setAuth({ token, user }) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    // localStorage unavailable - the caller's in-memory state still works
    // for this tab, it just won't survive a reload.
  }
}

export function clearAuth() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    // Nothing to fall back to - if localStorage is unavailable, there was
    // never anything persisted to clear in the first place.
  }
}

export function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}
