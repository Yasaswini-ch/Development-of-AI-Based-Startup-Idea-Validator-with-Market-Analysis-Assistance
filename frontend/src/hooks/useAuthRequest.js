import { useState } from 'react'

// Render's free-tier backend spins down after idling and can take 30-60s to
// wake on the first request. Without a notice, a sign-in button just sits
// on "One moment..." with no feedback, which reads as broken/stuck.
export const SLOW_REQUEST_NOTICE_MS = 6000

// Shared POST-to-/auth/* flow for every sign-in surface (AuthPanel's
// password form and Google button, the landing page's Google button):
// one submitting/waking/error state machine instead of a copy per page.
export default function useAuthRequest(apiUrl, onAuthenticated) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isWaking, setIsWaking] = useState(false)
  const [error, setError] = useState('')

  async function submit(path, body, fallbackError = 'Something went wrong. Please try again.') {
    setError('')
    setIsSubmitting(true)
    const wakeTimer = setTimeout(() => setIsWaking(true), SLOW_REQUEST_NOTICE_MS)
    try {
      const res = await fetch(`${apiUrl}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || fallbackError)
        return
      }
      onAuthenticated(data)
    } catch {
      setError('Could not reach the server. Please try again.')
    } finally {
      clearTimeout(wakeTimer)
      setIsSubmitting(false)
      setIsWaking(false)
    }
  }

  return { submit, isSubmitting, isWaking, error, setError }
}
