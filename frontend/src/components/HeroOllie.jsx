import { useState } from 'react'

const OLLIE_SRC = `${import.meta.env.BASE_URL}ollie.png`

// The small Ollie perched on the "B" of the hero headline. Hovering or focusing
// him (or tapping, on a touch screen) shows a one-line chat bubble.
export default function HeroOllie() {
  const [pinned, setPinned] = useState(false)
  const [hover, setHover] = useState(false)
  const show = pinned || hover

  return (
    <span
      className="absolute -left-1 -top-4 z-10 h-9 w-9 sm:-left-1 sm:-top-[1.65rem] sm:h-12 sm:w-12"
      data-testid="hero-ollie"
    >
      <button
        type="button"
        aria-label="Ollie says hi"
        aria-expanded={show}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        onClick={() => setPinned((p) => !p)}
        className="ollie-perch block h-full w-full cursor-pointer rounded-full outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <img src={OLLIE_SRC} alt="" className="h-full w-full object-contain" />
      </button>
      <span
        role="status"
        className={`pointer-events-none absolute bottom-full left-0 mb-1 whitespace-nowrap rounded-2xl rounded-bl-sm border border-border bg-panel px-3 py-1.5 font-sans text-sm font-normal not-italic leading-snug text-text shadow-lg transition-all duration-200 sm:bottom-auto sm:left-auto sm:right-full sm:top-1 sm:mb-0 sm:mr-2 sm:rounded-bl-2xl sm:rounded-br-sm ${
          show ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
        }`}
      >
        {show ? "Hi, I'm Ollie!" : ''}
      </span>
    </span>
  )
}
