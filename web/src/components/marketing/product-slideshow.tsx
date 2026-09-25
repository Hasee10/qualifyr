"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

/** Real HTML/CSS mini-mockups of the actual dashboard views, not screenshots - so this
 *  stays sharp at any zoom, themes with dark mode automatically, and never drifts out of
 *  sync with the real UI the way a screenshot would the moment a table column changes. */
const frames = [
  {
    label: "Overview",
    render: () => (
      <div className="grid grid-cols-3 gap-2 p-4">
        {["Qualified buyers", "Emails sent", "Replies"].map((t, i) => (
          <div key={t} className="rounded-lg bg-muted p-3">
            <p className="text-[10px] text-muted-foreground">{t}</p>
            <p className="mt-1 text-lg font-semibold">{[42, 118, 9][i]}</p>
          </div>
        ))}
        <div className="col-span-3 mt-1 flex h-20 items-end gap-1.5 rounded-lg bg-muted p-3">
          {[30, 55, 40, 70, 90, 60, 45].map((h, i) => (
            <div key={i} className="flex-1 rounded-sm bg-brand/60" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    ),
  },
  {
    label: "Campaigns",
    render: () => (
      <div className="flex flex-col gap-2 p-4">
        {[
          { name: "Retail & ecommerce, Islamabad", status: "Running", n: 96 },
          { name: "Live PPRA tenders, inventory", status: "Running", n: 24 },
          { name: "Textile & garment, Karachi", status: "Paused", n: 58 },
        ].map((c) => (
          <div key={c.name} className="flex items-center justify-between rounded-lg bg-muted px-3 py-2">
            <span className="truncate text-xs font-medium">{c.name}</span>
            <span className="flex items-center gap-2 text-[10px] text-muted-foreground">
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
    render: () => (
      <div className="p-4">
        <div className="overflow-hidden rounded-lg bg-muted">
          <div className="grid grid-cols-[1fr_auto_auto] gap-2 border-b border-border/60 px-3 py-2 text-[10px] text-muted-foreground">
            <span>Company</span><span>Score</span><span>Type</span>
          </div>
          {[
            { n: "RBS Interiors", s: 84, t: "BUYER" },
            { n: "Ittefaq Electronics", s: 77, t: "BUYER" },
            { n: "Al-Fateh Traders", s: 71, t: "BUYER" },
          ].map((l) => (
            <div key={l.n} className="grid grid-cols-[1fr_auto_auto] items-center gap-2 px-3 py-2 text-xs">
              <span className="truncate">{l.n}</span>
              <span className="rounded-full bg-brand-muted px-1.5 py-0.5 text-[10px] font-medium text-brand">{l.s}</span>
              <span className="text-[10px] text-muted-foreground">{l.t}</span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    label: "Outreach",
    render: () => (
      <div className="flex flex-col gap-2 p-4">
        <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-2">
          <span className="text-xs font-medium">3 drafts awaiting approval</span>
          <span className="rounded-full bg-brand text-brand-foreground px-2 py-0.5 text-[10px] font-medium">Review</span>
        </div>
        {[
          "Hi Ahmed, noticed RBS Interiors is hiring for retail ops...",
          "Hi Sana, saw the Series A news for Ittefaq...",
        ].map((t) => (
          <div key={t} className="rounded-lg border border-border/60 px-3 py-2 text-[11px] text-muted-foreground">
            {t}
          </div>
        ))}
      </div>
    ),
  },
]

export function ProductSlideshow() {
  const [index, setIndex] = React.useState(0)
  const [paused, setPaused] = React.useState(false)
  const reducedMotion = useReducedMotion()

  React.useEffect(() => {
    if (paused || reducedMotion) return
    const id = setInterval(() => setIndex((i) => (i + 1) % frames.length), 5000)
    return () => clearInterval(id)
  }, [paused, reducedMotion])

  return (
    <div
      className="mx-auto max-w-3xl"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      {/* Browser-chrome frame */}
      <div className="overflow-hidden rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 ring-1 ring-black/5">
        <div className="flex items-center gap-1.5 border-b border-border/60 bg-muted/50 px-3 py-2">
          <span className="size-2.5 rounded-full bg-red-400/70" />
          <span className="size-2.5 rounded-full bg-amber-400/70" />
          <span className="size-2.5 rounded-full bg-green-400/70" />
          <span className="ml-2 truncate rounded-md bg-background px-2 py-0.5 text-[10px] text-muted-foreground">
            app.qualifyr.com/{frames[index].label.toLowerCase()}
          </span>
        </div>
        <div className="min-h-[220px]">{frames[index].render()}</div>
      </div>

      <div className="mt-4 flex items-center justify-center gap-2">
        {frames.map((f, i) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setIndex(i)}
            aria-label={`Show ${f.label}`}
            aria-current={i === index}
            className={cn(
              "h-1.5 rounded-full transition-all",
              i === index ? "w-6 bg-brand" : "w-1.5 bg-muted-foreground/30 hover:bg-muted-foreground/50"
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
