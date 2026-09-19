import { useState } from 'react'
import { IconInfo } from './icons'

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

// Renders the sourceId markers after a claim, plus the popover with the
// cited source's title/url/snippet - the "click a claim, see its source"
// citation UI (docs/unique-features-plan.md §5.1). sourceIds that don't
// resolve in sourceMap (e.g. a claim tied to more results than the
// backend's compact_sources() limit) are silently skipped rather than
// shown as broken.
export default function Citation({ sourceIds, sourceMap }) {
  const [openIndex, setOpenIndex] = useState(null)
  const resolved = (sourceIds || [])
    .map((id) => ({ id, source: sourceMap.get(id) }))
    .filter((entry) => entry.source)

  if (resolved.length === 0) return null

  return (
    <span className="relative ml-1 inline-flex items-center gap-0.5 align-middle">
      {resolved.map((entry, index) => (
        <span key={entry.id} className="relative">
          <button
            type="button"
            onClick={() => setOpenIndex(openIndex === index ? null : index)}
            className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-accent/40 bg-accent/10 font-mono text-[9px] font-semibold text-accent hover:bg-accent/20"
            aria-label={`Show source for this claim`}
          >
            {index + 1}
          </button>
          {openIndex === index && (
            <div className="absolute left-1/2 top-6 z-10 w-64 -translate-x-1/2 rounded-lg border border-border bg-panel p-3 text-left shadow-lg">
              <p className="text-xs font-medium leading-snug text-text line-clamp-2">
                {entry.source.title || 'Untitled source'}
              </p>
              {entry.source.snippet && (
                <p className="mt-1 text-[11px] leading-relaxed text-muted line-clamp-3">
                  {entry.source.snippet}
                </p>
              )}
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[10px] uppercase tracking-wide text-muted/70">
                  {hostnameOf(entry.source.url)}
                </span>
                {entry.source.url && (
                  <a
                    href={entry.source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-accent hover:text-accent-hover"
                  >
                    <IconInfo className="h-3 w-3" />
                    View
                  </a>
                )}
              </div>
            </div>
          )}
        </span>
      ))}
    </span>
  )
}
