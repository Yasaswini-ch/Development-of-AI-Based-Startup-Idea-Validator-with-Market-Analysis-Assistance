import { useEffect, useRef, useState } from 'react'

// Platform Layer: Federated Google SSO (AFFINITY 5-pillar spec §4.6).
// Loads Google's own Identity Services script and renders its button into
// this component's div - the button's look/click handling is Google's,
// not ours, which is the point: users recognize it, and we never touch a
// password or handle the credential beyond forwarding the ID token to our
// own backend for verification (agent/google_auth.py).
//
// Renders nothing when VITE_GOOGLE_CLIENT_ID isn't set, same "quietly
// absent, never a broken button" rule the rest of this app takes with
// optional integrations - a deployment that hasn't configured Google
// sign-in just shows email/password only.
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
const _SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

let scriptLoadPromise = null

function loadGoogleScript() {
  if (scriptLoadPromise) return scriptLoadPromise
  scriptLoadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${_SCRIPT_SRC}"]`)
    if (existing) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = _SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Could not load Google Sign-In.'))
    document.head.appendChild(script)
  })
  return scriptLoadPromise
}

export default function GoogleSignInButton({ onCredential, onError }) {
  const containerRef = useRef(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!CLIENT_ID) return
    let cancelled = false

    loadGoogleScript()
      .then(() => {
        if (cancelled || !window.google || !containerRef.current) return
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (response) => {
            if (response?.credential) onCredential(response.credential)
          },
        })
        window.google.accounts.id.renderButton(containerRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          width: 320,
        })
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true)
          onError?.('Could not load Google Sign-In. Please use email and password instead.')
        }
      })

    return () => {
      cancelled = true
    }
  }, [onCredential, onError])

  if (!CLIENT_ID || failed) return null

  return <div ref={containerRef} className="flex justify-center" />
}
