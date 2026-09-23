import useCountUp from '../hooks/useCountUp'

const SIZE = 88
const STROKE = 7
const R = (SIZE - STROKE) / 2
const CIRC = 2 * Math.PI * R

// Ring stat — for the opportunity score (0-100), renders a filled arc
function RingStat({ value, max = 100, label, sub }) {
  const display = useCountUp(value ?? 0, 800)
  const pct = Math.min((display / max) * 100, 100)
  const filled = (pct / 100) * CIRC
  const gap = CIRC - filled

  const tier =
    pct >= 67 ? { stroke: 'var(--color-success)', text: 'text-success' }
    : pct >= 40 ? { stroke: 'var(--color-accent)',  text: 'text-accent'  }
    :             { stroke: 'var(--color-danger)',   text: 'text-danger'  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} className="-rotate-90">
          {/* Track */}
          <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none"
            stroke="var(--color-border)" strokeWidth={STROKE} />
          {/* Fill */}
          <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none"
            stroke={tier.stroke} strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${gap}`} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`font-serif text-xl font-semibold leading-none ${tier.text}`}>{display}</span>
          <span className="font-mono text-[8px] uppercase tracking-widest text-muted">/100</span>
        </div>
      </div>
      <div className="text-center">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-text">{label}</p>
        {sub && <p className="font-mono text-[9px] text-muted">{sub}</p>}
      </div>
    </div>
  )
}

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
        {sub && <p className="font-mono text-[9px] text-muted">{sub}</p>}
      </div>
    </div>
  )
}

export default function StatsStrip({ results, competitors, whiteSpace, marketOpportunity }) {
  const sourceCount     = results?.length ?? 0
  const competitorCount = competitors?.competitors?.length ?? 0
  const gapCount        = whiteSpace?.gaps?.length ?? 0
  const segmentCount    = marketOpportunity?.segments?.length ?? 0
  const oppScore        = marketOpportunity?.opportunityScore ?? null

  if (sourceCount === 0) return null

  return (
    <div className="rounded-2xl border border-border-strong bg-panel px-6 py-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-around gap-6">
        <CircleStat value={sourceCount}     label="Sources"     sub="Live web search"   color="var(--color-accent)" />
        <CircleStat value={competitorCount} label="Competitors" sub="Direct & indirect" color="var(--color-info)" />
        <CircleStat value={gapCount}        label="Market gaps" sub="Whitespace found"  color="var(--color-success)" />
        <CircleStat value={segmentCount}    label="Personas"    sub="Customer segments" color="var(--color-accent)" />
        {oppScore != null && (
          <RingStat value={oppScore} label="Opp. score" sub="Out of 100" />
        )}
      </div>
    </div>
  )
}
