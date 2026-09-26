import { useEffect, useRef, useState } from 'react'
import { IconLogOut, IconColumns, IconChevronDown } from './icons'

// Google accounts show their Google photo (avatarUrl, only ever set from a
// verified ID token - see backend/agent/auth.py); password accounts, or a
// photo that fails to load, show the email's first letter instead.
function Avatar({ user }) {
  const [broken, setBroken] = useState(false)
  if (user.avatarUrl && !broken) {
    return (
      <img
        src={user.avatarUrl}
        alt=""
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className="h-6 w-6 shrink-0 rounded-full border border-border object-cover"
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent font-sans text-[11px] font-semibold uppercase text-white"
    >
      {(user.email || '?').charAt(0)}
    </span>
  )
}

// Replaces the old row of separate History / Compare ideas / Dashboard /
// Platform health pills with a single account button that opens a dropdown -
// same destinations, one entry point instead of four competing for header
// space next to the account email.
export default function AccountMenu({ currentUser, onNavigate, onSignOut }) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined

    function handlePointerDown(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function go(view) {
    setOpen(false)
    onNavigate(view)
  }

  const items = [
    { view: 'history', label: 'History' },
    { view: 'compare', label: 'Compare ideas' },
    { view: 'analytics', label: 'Dashboard' },
  ]
  if (currentUser.isAdmin) {
    items.push({ view: 'platform-health', label: 'Platform health' })
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        title={`Signed in as ${currentUser.email}`}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-full border border-border bg-panel py-0.5 pl-0.5 pr-2.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
      >
        <Avatar user={currentUser} />
        <span className="hidden max-w-[9rem] truncate normal-case sm:inline">{currentUser.email}</span>
        <span className="sr-only sm:hidden">Account menu</span>
        <IconChevronDown className={`h-3 w-3 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+0.5rem)] z-20 w-56 overflow-hidden rounded-xl border border-border bg-panel py-1 shadow-lg"
        >
          <p className="truncate border-b border-border px-3 pb-2 pt-1.5 text-xs text-muted" title={currentUser.email}>
            {currentUser.email}
          </p>
          {items.map((item) => (
            <button
              key={item.view}
              type="button"
              role="menuitem"
              onClick={() => go(item.view)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:bg-surface hover:text-accent"
            >
              <IconColumns className="h-3.5 w-3.5 shrink-0" />
              {item.label}
            </button>
          ))}
          <div className="my-1 border-t border-border" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false)
              onSignOut()
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted transition-colors hover:bg-surface hover:text-danger"
          >
            <IconLogOut className="h-3.5 w-3.5 shrink-0" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
