const RADIUS = 46
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export default function ConfidenceGauge({ percent, size = 104, label = 'CONFIDENCE' }) {
  const offset = CIRCUMFERENCE - (CIRCUMFERENCE * percent) / 100

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 112 112"
      className="shrink-0"
      role="img"
      aria-label={`${label.toLowerCase()} ${percent}%`}
    >
      <circle cx="56" cy="56" r={RADIUS} fill="none" stroke="var(--color-border)" strokeWidth="10" />
      <circle
        cx="56"
        cy="56"
        r={RADIUS}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={offset}
        transform="rotate(-90 56 56)"
        style={{ transition: 'stroke-dashoffset 0.2s linear' }}
      />
      <text x="56" y="53" textAnchor="middle" className="font-serif" style={{ fontSize: 22, fill: 'var(--color-text)' }}>
        {percent}%
      </text>
      <text
        x="56"
        y="71"
        textAnchor="middle"
        className="font-mono"
        style={{ fontSize: 8, letterSpacing: '0.08em', fill: 'var(--color-muted)' }}
      >
        {label}
      </text>
    </svg>
  )
}
