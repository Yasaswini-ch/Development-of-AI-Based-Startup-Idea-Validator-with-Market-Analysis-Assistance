# Frontend Design Spec — Idea Submission Interface

**Stack**: React (Vite) + Tailwind CSS. No component library — build custom for a
distinct, non-templated feel.

## Layout
- Centered single-column form, max-width ~640px, generous vertical rhythm (not
  edge-to-edge, not cramped)
- Hero/header: product name + one-line tagline, minimal
- Form card: soft shadow, rounded corners (`rounded-2xl`), subtle border — feels like a
  "panel," not a raw form
- Results section appears below the form after submission (same page, smooth
  scroll/fade-in — no jarring reload)

## Palette
- Neutral-dark base (near-black or deep navy background) OR clean white — pick one,
  don't mix light/dark half-heartedly
- One accent color (e.g. indigo/violet or emerald) used sparingly — CTA button, active
  states, metric highlights
- Avoid default Tailwind blue-500/gray palette as-is; tune shades so it doesn't look
  like a template

## Typography
- One display font for headings (e.g. Inter Tight, Geist, or similar modern sans), one
  for body — or one family at varied weights
- Clear hierarchy: large bold heading, muted subtext, readable form labels (not
  placeholder-only labels)

## Components Needed
1. `IdeaForm` — idea (textarea), target customer (input), problem (textarea), submit
   button with loading state
2. `SubmitButton` — disabled/loading/default states, subtle hover transition
3. `ValidationResults` — renders search-agent output: summary + market/competitor cards
   (grid of 2–3 cards, not a wall of text)
4. `EmptyState` / `ErrorState` — for no results or failed API call (must not just blank
   out)

## Interaction Details ("premium," not "vibecoded")
- Button and input hover/focus states (subtle scale or border-color transition, not
  default browser outline)
- Loading spinner or skeleton while waiting on the Tavily search agent — never a frozen
  UI
- Form validation inline (e.g. red border + message under empty idea field), not a
  browser alert
- Consistent spacing scale (stick to Tailwind's default spacing tokens, don't hand-pick
  random px values)

## API Contract
See [`milestone1-plan.md`](milestone1-plan.md) for the full contract. Summary:

```
POST /validate
Request:  { idea, targetCustomer, problem }
Response: { summary, results: [{ title, snippet, url }] }
```
