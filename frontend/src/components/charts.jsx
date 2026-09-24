// Small, dependency-free inline-SVG chart primitives shared by
// AnalyticsDashboard.jsx and PlatformHealth.jsx - this project has no
// charting library anywhere (see ConfidenceGauge.jsx for the existing
// hand-rolled-SVG convention this follows), so these stay consistent with
// that rather than introducing one just for two dashboards.

const PALETTE = {
  accent: 'var(--color-accent)',
  success: 'var(--color-success)',
  info: 'var(--color-info)',
  danger: 'var(--color-danger)',
  muted: 'var(--color-muted)',
  border: 'var(--color-border)',
  text: 'var(--color-text)',
}

export const CHART_COLORS = [PALETTE.accent, PALETTE.success, PALETTE.info, 'var(--color-accent-hover)', PALETTE.danger, PALETTE.muted]

function EmptyChart({ label = 'Not enough data yet' }) {
  return (
    <div className="flex h-full min-h-[120px] items-center justify-center rounded-lg border border-dashed border-border font-mono text-[11px] uppercase tracking-wide text-muted">
      {label}
    </div>
  )
}

// --------------------------------------------------
// Line / area chart - score trend, daily volume, cache efficiency
// --------------------------------------------------

export function LineChart({ points, height = 160, color = PALETTE.accent, filled = true, yMin, yMax, valueSuffix = '' }) {
  if (!points || points.length === 0) return <EmptyChart />

  const values = points.map((p) => p.y)
  const min = yMin ?? Math.min(...values, 0)
  const max = yMax ?? Math.max(...values, 1)
  const range = max - min || 1
  const width = 100
  const stepX = points.length > 1 ? width / (points.length - 1) : 0

  const coords = points.map((p, i) => ({
    x: points.length > 1 ? i * stepX : width / 2,
    y: height - ((p.y - min) / range) * height,
  }))

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ')
  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${height} L ${coords[0].x} ${height} Z`

  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible" role="img" aria-label="Line chart">
      {filled && <path d={areaPath} fill={color} opacity={0.12} />}
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      {coords.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={1.6} fill={color} vectorEffect="non-scaling-stroke">
          <title>
            {points[i].label}: {points[i].y}
            {valueSuffix}
          </title>
        </circle>
      ))}
    </svg>
  )
}

// --------------------------------------------------
// Horizontal bar chart - score by idea, node success rate, latency by node,
// top categories
// --------------------------------------------------

export function HBarChart({ rows, valueSuffix = '', formatValue }) {
  if (!rows || rows.length === 0) return <EmptyChart />
  const max = Math.max(...rows.map((r) => r.max ?? r.value), 1)

  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <div className="w-28 shrink-0 truncate text-muted" title={row.label}>
            {row.label}
          </div>
          <div className="h-1.5 flex-1 rounded-full bg-border">
            <div
              className="h-full rounded-full"
              style={{ width: `${Math.max(2, (row.value / max) * 100)}%`, background: row.color || PALETTE.accent }}
            />
          </div>
          <div className="w-14 shrink-0 text-right font-mono text-[11px] text-text">
            {formatValue ? formatValue(row.value) : row.value}
            {valueSuffix}
          </div>
        </div>
      ))}
    </div>
  )
}

// --------------------------------------------------
// Stacked horizontal bar chart - assumption risk by category
// --------------------------------------------------

export function StackedHBarChart({ rows, legend }) {
  if (!rows || rows.length === 0) return <EmptyChart />
  const max = Math.max(...rows.map((r) => r.segments.reduce((sum, s) => sum + s.value, 0)), 1)

  return (
    <div className="flex flex-col gap-3">
      {legend && (
        <div className="flex flex-wrap gap-3 text-[11px] text-muted">
          {legend.map((item) => (
            <span key={item.label} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm" style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      )}
      {rows.map((row, i) => {
        const total = row.segments.reduce((sum, s) => sum + s.value, 0)
        return (
          <div key={i} className="flex items-center gap-2 text-xs">
            <div className="w-24 shrink-0 truncate text-muted" title={row.label}>
              {row.label}
            </div>
            <div className="flex h-2.5 flex-1 overflow-hidden rounded-full bg-border">
              {total === 0
                ? null
                : row.segments.map((seg, j) =>
                    seg.value > 0 ? (
                      <div key={j} style={{ width: `${(seg.value / max) * 100}%`, background: seg.color }} title={`${seg.label}: ${seg.value}`} />
                    ) : null,
                  )}
            </div>
            <div className="w-6 shrink-0 text-right font-mono text-[11px] text-muted">{total}</div>
          </div>
        )
      })}
    </div>
  )
}

// --------------------------------------------------
// Radar chart - viability dimensions
// --------------------------------------------------

export function RadarChart({ axes, max = 100, color = PALETTE.accent, size = 200 }) {
  if (!axes || axes.length < 3) return <EmptyChart label="Needs at least 3 dimensions" />
  const center = size / 2
  const radius = size / 2 - 28
  const angleStep = (Math.PI * 2) / axes.length

  const pointFor = (value, index) => {
    const angle = angleStep * index - Math.PI / 2
    const r = (Math.max(0, Math.min(value, max)) / max) * radius
    return { x: center + r * Math.cos(angle), y: center + r * Math.sin(angle) }
  }

  const dataPoints = axes.map((a, i) => pointFor(a.value, i))
  const dataPath = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z'

  const rings = [0.33, 0.66, 1]

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto h-full w-full" role="img" aria-label="Radar chart">
      {rings.map((fraction) => (
        <polygon
          key={fraction}
          points={axes.map((_, i) => { const p = pointFor(max * fraction, i); return `${p.x},${p.y}` }).join(' ')}
          fill="none"
          stroke={PALETTE.border}
          strokeWidth={1}
        />
      ))}
      {axes.map((_, i) => {
        const p = pointFor(max, i)
        return <line key={i} x1={center} y1={center} x2={p.x} y2={p.y} stroke={PALETTE.border} strokeWidth={1} />
      })}
      <path d={dataPath} fill={color} fillOpacity={0.18} stroke={color} strokeWidth={1.5} />
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={2.5} fill={color}>
          <title>
            {axes[i].label}: {axes[i].value}
          </title>
        </circle>
      ))}
      {axes.map((a, i) => {
        const p = pointFor(max * 1.22, i)
        return (
          <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="middle" className="font-mono" style={{ fontSize: 7, fill: PALETTE.muted }}>
            {a.label}
          </text>
        )
      })}
    </svg>
  )
}

// --------------------------------------------------
// Donut chart - revenue model distribution, Groq model usage
// --------------------------------------------------

export function DonutChart({ slices, size = 160 }) {
  const total = (slices || []).reduce((sum, s) => sum + s.value, 0)
  if (!slices || slices.length === 0 || total === 0) return <EmptyChart />

  const radius = size / 2
  const inner = radius * 0.62
  let cumulative = 0

  const arcs = slices.map((slice) => {
    const startAngle = (cumulative / total) * Math.PI * 2 - Math.PI / 2
    cumulative += slice.value
    const endAngle = (cumulative / total) * Math.PI * 2 - Math.PI / 2
    const largeArc = endAngle - startAngle > Math.PI ? 1 : 0

    const outer = (angle, r) => [radius + r * Math.cos(angle), radius + r * Math.sin(angle)]
    const [ox1, oy1] = outer(startAngle, radius)
    const [ox2, oy2] = outer(endAngle, radius)
    const [ix1, iy1] = outer(endAngle, inner)
    const [ix2, iy2] = outer(startAngle, inner)

    const path = [
      `M ${ox1} ${oy1}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${ox2} ${oy2}`,
      `L ${ix1} ${iy1}`,
      `A ${inner} ${inner} 0 ${largeArc} 0 ${ix2} ${iy2}`,
      'Z',
    ].join(' ')

    return { path, color: slice.color, label: slice.label, value: slice.value, pct: Math.round((slice.value / total) * 100) }
  })

  return (
    <div className="flex items-center gap-4">
      <svg viewBox={`0 0 ${size} ${size}`} className="h-32 w-32 shrink-0" role="img" aria-label="Donut chart">
        {arcs.map((arc, i) => (
          <path key={i} d={arc.path} fill={arc.color}>
            <title>
              {arc.label}: {arc.pct}%
            </title>
          </path>
        ))}
      </svg>
      <ul className="flex flex-col gap-1.5 text-xs">
        {arcs.map((arc, i) => (
          <li key={i} className="flex items-center gap-1.5 text-muted">
            <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: arc.color }} />
            <span className="truncate">{arc.label}</span>
            <span className="font-mono text-text">{arc.pct}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function TagCloud({ tags, tone = 'default' }) {
  if (!tags || tags.length === 0) return <p className="text-xs text-muted">Not enough data yet.</p>
  const max = Math.max(...tags.map((t) => t.count), 1)
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => {
        const strong = tag.count / max >= 0.6
        const cls =
          tone === 'risk'
            ? strong
              ? 'border-danger/30 bg-danger/10 text-danger font-medium'
              : 'border-border bg-surface text-muted'
            : strong
              ? 'border-accent-hover/30 bg-accent/10 text-accent font-medium'
              : 'border-border bg-surface text-muted'
        return (
          <span key={tag.text} className={`rounded-full border px-2.5 py-1 text-[11px] ${cls}`}>
            {tag.text}
            {tag.count > 1 ? ` (${tag.count})` : ''}
          </span>
        )
      })}
    </div>
  )
}

export { EmptyChart, PALETTE }
