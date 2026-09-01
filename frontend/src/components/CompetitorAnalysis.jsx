import { IconShield, IconAlertTriangle } from './icons'

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

function Badge({ label, value }) {
  if (!value || value === 'unknown') return null
  return (
    <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted">
      {label}: {value}
    </span>
  )
}

function CompetitorCard({ competitor }) {
  const { name, offering, url, gap, estimatedPrice, featureBreadth } = competitor
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="block rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent"
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-text">{name}</h4>
      </div>
      <p className="mt-1 text-sm text-muted leading-snug">{offering}</p>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge label="Price" value={estimatedPrice} />
        <Badge label="Breadth" value={featureBreadth} />
      </div>

      <div className="mt-3 flex items-start gap-1.5 border-t border-border pt-2">
        <IconAlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <p className="text-sm text-text leading-snug">{gap}</p>
      </div>

      {url && (
        <p className="mt-2 truncate font-mono text-[11px] uppercase tracking-wide text-muted/60">
          {hostnameOf(url)}
        </p>
      )}
    </a>
  )
}

export default function CompetitorAnalysis({ data }) {
  if (!data) return null

  const { competitors = [] } = data
  if (competitors.length === 0) return null

  return (
    <div className="mx-auto mt-6 max-w-xl rounded-2xl border border-border bg-panel p-6 shadow-sm sm:p-8">
      <div className="flex items-center gap-2">
        <IconShield className="h-4 w-4 text-accent" />
        <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
          Competitor Analysis
        </h2>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {competitors.map((c, i) => (
          <CompetitorCard key={i} competitor={c} />
        ))}
      </div>
    </div>
  )
}
