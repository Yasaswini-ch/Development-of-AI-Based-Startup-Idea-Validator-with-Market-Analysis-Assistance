import { IconAlertTriangle, IconGlobe, IconTrendingUp, IconUsers } from './icons'
import DegradedBanner from './DegradedBanner'

export default function GtmStrategy({ data, error }) {
  if (data === null || data === undefined) {
    return (
      <div className="flex flex-col items-center justify-center p-2 text-center">
        <IconAlertTriangle className="h-5 w-5 text-muted" />
        <p className="mt-2 text-sm font-medium text-text">Go-to-market strategy wasn&apos;t available</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          {error || 'This analysis failed to complete for this request.'}
        </p>
      </div>
    )
  }

  const channels = Array.isArray(data.channels) ? data.channels : []

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {data.degraded && (
        <div className="md:col-span-2">
          <DegradedBanner />
        </div>
      )}
      <section className="rounded-xl border border-accent/30 bg-accent/5 p-5 md:col-span-2">
        <h3 className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconTrendingUp className="h-4 w-4 text-accent" />
          Positioning
        </h3>
        <p className="mt-3 text-sm leading-relaxed text-text">
          {data.positioning || 'No positioning recommendation was generated.'}
        </p>
      </section>

      <section className="rounded-xl border border-border bg-surface p-5">
        <h3 className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconGlobe className="h-4 w-4 text-accent" />
          Priority channels
        </h3>
        {channels.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {channels.map((channel, index) => (
              <span key={index} className="rounded-full border border-border bg-panel px-3 py-1 text-sm text-text">
                {channel}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted">No channels were recommended.</p>
        )}
      </section>

      <section className="rounded-xl border border-border bg-surface p-5">
        <h3 className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted">
          <IconUsers className="h-4 w-4 text-accent" />
          First customers
        </h3>
        <p className="mt-3 text-sm leading-relaxed text-text">
          {data.earlyCustomerApproach || 'No early-customer approach was generated.'}
        </p>
      </section>
    </div>
  )
}
