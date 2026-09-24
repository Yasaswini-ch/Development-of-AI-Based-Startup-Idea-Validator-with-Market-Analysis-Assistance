import { useEffect, useRef, useState } from 'react'
import { IconUser, IconLogOut, IconColumns, IconChevronDown } from './icons'

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
        className="flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
      >
        <IconUser className="h-3 w-3 text-accent" />
        <span className="max-w-[9rem] truncate normal-case">{currentUser.email}</span>
        <IconChevronDown className={`h-3 w-3 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+0.5rem)] z-20 w-48 overflow-hidden rounded-xl border border-border bg-panel py-1 shadow-lg"
        >
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
