import useCountUp from '../hooks/useCountUp'

const SIZE = 88
const STROKE = 7
const R = (SIZE - STROKE) / 2

// Circle stat — for counts, renders a solid decorative ring with number inside
function CircleStat({ value, label, sub, color = 'var(--color-accent)' }) {
  const display = useCountUp(value ?? 0, 600)

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE}>
          {/* Outer ring decoration */}
          <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none"
            stroke="var(--color-border)" strokeWidth={STROKE} />
          {/* Subtle filled arc (always full, decorative) */}
          <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none"
            stroke={color} strokeWidth={STROKE} opacity="0.25" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-serif text-2xl font-semibold leading-none text-text">{display}</span>
        </div>
      </div>
      <div className="text-center">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-text">{label}</p>
        {sub && <p className="font-mono text-[10.5px] text-muted">{sub}</p>}
      </div>
    </div>
  )
}

export default function StatsStrip({ results, competitors, whiteSpace, marketOpportunity }) {
  const sourceCount     = results?.length ?? 0
  const competitorCount = competitors?.competitors?.length ?? 0
  // white_space.py returns the gaps under "opportunities" (same field
  // WhiteSpaceAnalysis renders); there is no "gaps" key.
  const gapCount        = whiteSpace?.opportunities?.length ?? 0
  const segmentCount    = marketOpportunity?.segments?.length ?? 0

  if (sourceCount === 0) return null

  return (
    <div className="rounded-2xl border border-border-strong bg-panel px-6 py-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-around gap-6">
        <CircleStat value={sourceCount}     label="Sources"     sub="Live web search"   color="var(--color-accent)" />
        <CircleStat value={competitorCount} label="Competitors" sub="Direct & indirect" color="var(--color-info)" />
        <CircleStat value={gapCount}        label="Market gaps" sub="Whitespace found"  color="var(--color-success)" />
        <CircleStat value={segmentCount}    label="Personas"    sub="Customer segments" color="var(--color-accent)" />
      </div>
    </div>
  )
}
