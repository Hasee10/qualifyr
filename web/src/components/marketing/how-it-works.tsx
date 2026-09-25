const steps = [
  {
    n: "01",
    title: "Define your campaign",
    description: "A YAML file: geography, industry, buyer terms, minimum score. No code, no UI form to fight.",
    frame: (
      <div className="p-3">
        <div className="flex items-center justify-between rounded-md bg-muted px-2.5 py-1.5 text-[10px]">
          <span className="text-muted-foreground">Geography</span>
          <span className="font-medium">Islamabad, Rawalpindi</span>
        </div>
        <div className="mt-1.5 flex items-center justify-between rounded-md bg-muted px-2.5 py-1.5 text-[10px]">
          <span className="text-muted-foreground">Min. score</span>
          <span className="font-medium">70</span>
        </div>
      </div>
    ),
  },
  {
    n: "02",
    title: "We discover and qualify",
    description: "Companies are pulled from public sources, classified buyer vs. vendor, and scored with a written reason for every point.",
    frame: (
      <div className="p-3">
        <div className="flex items-center justify-between rounded-md bg-muted px-2.5 py-1.5 text-[10px]">
          <span className="truncate">RBS Interiors</span>
          <span className="rounded-full bg-brand-muted px-1.5 py-0.5 font-medium text-brand">84</span>
        </div>
        <div className="mt-1.5 flex items-center justify-between rounded-md bg-muted px-2.5 py-1.5 text-[10px]">
          <span className="truncate">Ittefaq Electronics</span>
          <span className="rounded-full bg-brand-muted px-1.5 py-0.5 font-medium text-brand">77</span>
        </div>
      </div>
    ),
  },
  {
    n: "03",
    title: "Approve and send",
    description: "Review the queue, approve what looks right, and outreach goes out from your own mailbox — never automatically.",
    frame: (
      <div className="p-3">
        <div className="rounded-md bg-muted px-2.5 py-1.5 text-[10px] text-muted-foreground">
          Hi Ahmed, noticed RBS Interiors is hiring...
        </div>
        <div className="mt-1.5 flex justify-end">
          <span className="rounded-full bg-brand px-2 py-0.5 text-[10px] font-medium text-brand-foreground">
            Approve
          </span>
        </div>
      </div>
    ),
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-y bg-muted/30 py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <p className="text-center text-xs font-medium uppercase tracking-wide text-brand">The process</p>
        <div className="mx-auto mt-3 max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">From campaign to first reply</h2>
          <p className="mt-4 text-muted-foreground">
            No dashboards to configure before you start &mdash; define a campaign and the
            pipeline runs.
          </p>
        </div>

        <div className="mt-14 grid gap-10 sm:grid-cols-3">
          {steps.map((s) => (
            <div key={s.n}>
              <div className="overflow-hidden rounded-lg border border-border/60 bg-card shadow-sm">
                <div className="flex items-center gap-1 border-b border-border/60 bg-muted/50 px-2.5 py-1.5">
                  <span className="size-1.5 rounded-full bg-red-400/60" />
                  <span className="size-1.5 rounded-full bg-amber-400/60" />
                  <span className="size-1.5 rounded-full bg-green-400/60" />
                </div>
                {s.frame}
              </div>
              <p className="mt-6 font-heading text-5xl font-bold text-brand/15">{s.n}</p>
              <h3 className="-mt-4 font-heading text-lg font-medium">{s.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{s.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
