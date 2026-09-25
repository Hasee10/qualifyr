"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

/** Real HTML/CSS mini-mockups of the actual dashboard views, not screenshots - so this
 *  stays sharp at any zoom, themes with dark mode automatically, and never drifts out of
 *  sync with the real UI the way a screenshot would the moment a table column changes.
 *
 *  Presented as a guided demo: a synthetic cursor walks the tabs, clicks each one, and the
 *  view settles in - the deliberate pacing (read, move, click, read) reads as a product
 *  tour rather than a slideshow. `route` is the real app path, so the address bar matches
 *  the routes in app/(app)/ instead of an invented "/overview". */
const frames = [
  {
    label: "Overview",
    route: "dashboard",
    render: () => (
      <div className="grid grid-cols-3 gap-2.5 p-5">
        {["Qualified buyers", "Emails sent", "Replies"].map((t, i) => (
          <div key={t} className="qf-rise rounded-lg bg-muted p-3" style={{ animationDelay: `${i * 70}ms` }}>
            <p className="text-[10px] text-muted-foreground">{t}</p>
            <p className="mt-1 text-lg font-semibold">{[42, 118, 9][i]}</p>
          </div>
        ))}
        <div className="qf-rise col-span-3 mt-1 flex h-24 items-end gap-1.5 rounded-lg bg-muted p-3" style={{ animationDelay: "220ms" }}>
          {[30, 55, 40, 70, 90, 60, 45].map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-sm bg-brand/60"
              style={{ height: `${h}%`, animationDelay: `${280 + i * 45}ms` }}
            />
          ))}
        </div>
      </div>
    ),
  },
  {
    label: "Campaigns",
    route: "campaigns",
    render: () => (
      <div className="flex flex-col gap-2.5 p-5">
        {[
          { name: "Retail & ecommerce, Islamabad", status: "Running", n: 96 },
          { name: "Live PPRA tenders, inventory", status: "Running", n: 24 },
          { name: "Textile & garment, Karachi", status: "Paused", n: 58 },
        ].map((c, i) => (
          <div
            key={c.name}
            className="qf-rise flex items-center justify-between rounded-lg bg-muted px-3 py-2.5"
            style={{ animationDelay: `${i * 90}ms` }}
          >
            <span className="truncate text-xs font-medium">{c.name}</span>
            <span className="flex shrink-0 items-center gap-2 text-[10px] text-muted-foreground">
              {c.n} leads
              <span className={cn("rounded-full px-1.5 py-0.5", c.status === "Running" ? "bg-brand-muted text-brand" : "bg-secondary")}>
                {c.status}
              </span>
            </span>
          </div>
        ))}
      </div>
    ),
  },
  {
    label: "Leads",
    route: "leads",
    render: () => (
      <div className="p-5">
        <div className="overflow-hidden rounded-lg bg-muted">
          <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border/60 px-3 py-2 text-[10px] text-muted-foreground">
            <span>Company</span><span>Score</span><span>Type</span>
          </div>
          {[
            { n: "RBS Interiors", s: 84, t: "BUYER" },
            { n: "Ittefaq Electronics", s: 77, t: "BUYER" },
            { n: "Al-Fateh Traders", s: 71, t: "BUYER" },
          ].map((l, i) => (
            <div
              key={l.n}
              className="qf-rise grid grid-cols-[1fr_auto_auto] items-center gap-3 px-3 py-2.5 text-xs"
              style={{ animationDelay: `${i * 90}ms` }}
            >
              <span className="truncate">{l.n}</span>
              <span className="justify-self-center rounded-full bg-brand-muted px-1.5 py-0.5 text-[10px] font-medium text-brand">{l.s}</span>
              <span className="text-[10px] text-muted-foreground">{l.t}</span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    label: "Outreach",
    route: "outreach",
    render: () => (
      <div className="flex flex-col gap-2.5 p-5">
        <div className="qf-rise flex items-center justify-between rounded-lg bg-muted px-3 py-2.5">
          <span className="text-xs font-medium">3 drafts awaiting approval</span>
          <span className="rounded-full bg-brand px-2 py-0.5 text-[10px] font-medium text-brand-foreground">Review</span>
        </div>
        {[
          "Hi Ahmed, noticed RBS Interiors is hiring for retail ops...",
          "Hi Sana, saw Ittefaq just opened a second Lahore branch...",
        ].map((t, i) => (
          <div
            key={t}
            className="qf-rise rounded-lg border border-border/60 px-3 py-2.5 text-[11px] text-muted-foreground"
            style={{ animationDelay: `${(i + 1) * 90}ms` }}
          >
            {t}
          </div>
        ))}
      </div>
    ),
  },
]

// Deliberate, unhurried pacing. Read the view, then the cursor travels and clicks.
const DWELL_MS = 3600      // time to read the current view before moving on
const TRAVEL_MS = 900      // cursor glide to the next tab
const CLICK_MS = 260       // press-and-release before the view switches

export function ProductSlideshow() {
  const [active, setActive] = React.useState(0)
  const [paused, setPaused] = React.useState(false)
  const [clicking, setClicking] = React.useState(false)
  const [cursor, setCursor] = React.useState<{ x: number; y: number } | null>(null)
  const reducedMotion = useReducedMotion()

  const frameRef = React.useRef<HTMLDivElement>(null)
  const tabRefs = React.useRef<(HTMLButtonElement | null)[]>([])
  const activeRef = React.useRef(0)
  activeRef.current = active

  // Centre of a tab, in coordinates local to the demo frame.
  const tabCenter = React.useCallback((i: number) => {
    const tab = tabRefs.current[i]
    const frame = frameRef.current
    if (!tab || !frame) return null
    const t = tab.getBoundingClientRect()
    const f = frame.getBoundingClientRect()
    return { x: t.left - f.left + t.width / 2, y: t.top - f.top + t.height / 2 }
  }, [])

  // Park the cursor on the active tab once laid out, and keep it there on resize.
  React.useLayoutEffect(() => {
    if (reducedMotion) return
    const place = () => {
      const c = tabCenter(activeRef.current)
      if (c) setCursor(c)
    }
    place()
    window.addEventListener("resize", place)
    return () => window.removeEventListener("resize", place)
  }, [tabCenter, reducedMotion])

  // The guided-tour driver: dwell → glide → click → switch → repeat.
  React.useEffect(() => {
    if (paused || reducedMotion) return
    const timers: ReturnType<typeof setTimeout>[] = []
    const after = (ms: number, fn: () => void) => timers.push(setTimeout(fn, ms))

    const step = () => {
      after(DWELL_MS, () => {
        const next = (activeRef.current + 1) % frames.length
        const c = tabCenter(next)
        if (c) setCursor(c)                         // CSS transition glides the cursor
        after(TRAVEL_MS, () => {
          setClicking(true)
          after(CLICK_MS, () => {
            setClicking(false)
            setActive(next)                          // content crossfades/rises in
            step()
          })
        })
      })
    }
    step()
    return () => timers.forEach(clearTimeout)
  }, [paused, reducedMotion, tabCenter])

  const jumpTo = (i: number) => {
    const c = tabCenter(i)
    if (c) setCursor(c)
    setActive(i)
  }

  return (
    <div
      className="relative mx-auto max-w-3xl"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      {/* Soft brand glow so the pane reads as a lit surface, not a flat card. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-x-8 -top-10 bottom-0 -z-10 opacity-60 blur-3xl"
        style={{ background: "radial-gradient(60% 60% at 50% 0%, var(--brand-muted), transparent 70%)" }}
      />

      {/* Browser-chrome frame */}
      <div ref={frameRef} className="relative overflow-hidden rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/20 ring-1 ring-black/5">
        <div className="flex items-center gap-1.5 border-b border-border/60 bg-muted/50 px-3 py-2.5">
          <span className="size-2.5 rounded-full bg-red-400/70" />
          <span className="size-2.5 rounded-full bg-amber-400/70" />
          <span className="size-2.5 rounded-full bg-green-400/70" />
          <span className="ml-2 flex-1 truncate rounded-md bg-background px-2.5 py-1 text-[10px] text-muted-foreground">
            app.qualifyr.com/{frames[active].route}
          </span>
        </div>

        {/* Tab bar - the cursor's targets, and real manual controls. */}
        <div role="tablist" aria-label="Product views" className="flex gap-1 border-b border-border/60 bg-muted/30 px-2 py-1.5">
          {frames.map((f, i) => (
            <button
              key={f.label}
              ref={(el) => { tabRefs.current[i] = el }}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => jumpTo(i)}
              className={cn(
                "rounded-md px-3 py-1.5 text-[11px] font-medium transition-colors",
                i === active ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Content - fixed height so the pane never jumps as views change. */}
        <div className="h-[248px]">
          <div key={active} className="h-full">
            {frames[active].render()}
          </div>
        </div>

        {/* Synthetic cursor. Purely decorative, so hidden from assistive tech and under
            reduced-motion. Travels via a transform transition; a ring pulses on click. */}
        {cursor && !reducedMotion && (
          <div
            aria-hidden
            className="pointer-events-none absolute left-0 top-0 z-20"
            style={{
              transform: `translate(${cursor.x}px, ${cursor.y}px)`,
              transition: `transform ${TRAVEL_MS}ms cubic-bezier(0.5, 0, 0.2, 1)`,
            }}
          >
            <div className="relative -translate-x-[3px] -translate-y-[2px]">
              <span
                className={cn(
                  "absolute left-0 top-0 size-7 -translate-x-1/2 -translate-y-1/2 rounded-full border border-brand/50 transition-all duration-200",
                  clicking ? "scale-100 opacity-60" : "scale-0 opacity-0"
                )}
              />
              <svg width="20" height="20" viewBox="0 0 20 20" className={cn("drop-shadow-md transition-transform duration-150", clicking && "scale-90")}>
                <path d="M3 2l5.5 13 2-5 5-2L3 2z" className="fill-foreground stroke-background" strokeWidth="1.25" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        )}
      </div>

      {/* Progress dots - reflect the tour, and stay clickable. */}
      <div className="mt-5 flex items-center justify-center gap-2">
        {frames.map((f, i) => (
          <button
            key={f.label}
            type="button"
            onClick={() => jumpTo(i)}
            aria-label={`Show ${f.label}`}
            aria-current={i === active}
            className={cn(
              "h-1.5 rounded-full transition-all",
              i === active ? "w-6 bg-brand" : "w-1.5 bg-muted-foreground/30 hover:bg-muted-foreground/50"
            )}
          />
        ))}
      </div>
    </div>
  )
}

function useReducedMotion() {
  const [reduced, setReduced] = React.useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  )
  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [])
  return reduced
}
