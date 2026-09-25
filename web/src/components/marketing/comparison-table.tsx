import { Check, X } from "lucide-react"

const rows = [
  {
    task: "Finding companies to reach out to",
    without: "A directory, scrolled by hand",
    with: "Auto-discovered from 8 public sources",
  },
  {
    task: "Telling buyers from vendors",
    without: "Guesswork from the homepage",
    with: "Classified automatically, with evidence",
  },
  {
    task: "Deciding who's worth a call",
    without: "Gut feeling",
    with: "A 0–100 score with a written reason",
  },
  {
    task: "Catching hiring or funding signals",
    without: "Usually you don't, until it's old news",
    with: "Surfaced with a source link, same run",
  },
  {
    task: "Sending the first email",
    without: "Manual research per contact",
    with: "A drafted email, queued for your approval",
  },
]

/** Not a competitor comparison - a comparison against how this gets done without a tool,
 *  same shape as the reference's table but honest about what a lead engine replaces. */
export function ComparisonTable() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          What most teams do today, vs. Qualifyr
        </h2>
        <p className="mt-4 text-muted-foreground">
          Not a competitor comparison &mdash; a comparison against how this actually gets
          done without a tool.
        </p>
      </div>

      <div className="mt-14 overflow-hidden rounded-xl border border-border/60">
        <div className="grid grid-cols-2 border-b border-border/60 bg-muted/30 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <div className="px-6 py-3">Without Qualifyr</div>
          <div className="px-6 py-3 text-brand">With Qualifyr</div>
        </div>
        {rows.map((r) => (
          <div key={r.task} className="grid grid-cols-2 not-last:border-b border-border/60">
            <div className="flex items-start gap-2.5 px-6 py-4 text-sm text-muted-foreground">
              <X className="mt-0.5 size-4 shrink-0 text-destructive/70" />
              <span>
                <span className="block text-xs text-muted-foreground/70">{r.task}</span>
                {r.without}
              </span>
            </div>
            <div className="flex items-start gap-2.5 border-l border-border/60 bg-brand-muted/30 px-6 py-4 text-sm">
              <Check className="mt-0.5 size-4 shrink-0 text-brand" />
              <span>{r.with}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
