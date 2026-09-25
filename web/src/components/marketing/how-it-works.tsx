const steps = [
  {
    n: "01",
    title: "Define your campaign",
    description: "A YAML file: geography, industry, buyer terms, minimum score. No code, no UI form to fight.",
  },
  {
    n: "02",
    title: "We discover and qualify",
    description: "Companies are pulled from public sources, classified buyer vs. vendor, and scored with a written reason for every point.",
  },
  {
    n: "03",
    title: "Approve and send",
    description: "Review the queue, approve what looks right, and outreach goes out from your own mailbox — never automatically.",
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-y bg-muted/30 py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">How it works</h2>
          <p className="mt-4 text-muted-foreground">Three steps, and you are in control at the last one.</p>
        </div>

        <div className="relative mt-14 grid gap-10 sm:grid-cols-3">
          {/* Connecting line behind the numerals, desktop only. */}
          <div aria-hidden className="absolute inset-x-0 top-6 hidden h-px bg-border sm:block" />
          {steps.map((s) => (
            <div key={s.n} className="relative text-center sm:text-left">
              <span className="relative z-10 inline-flex size-12 items-center justify-center rounded-full bg-background font-heading text-lg font-semibold text-brand ring-1 ring-border">
                {s.n}
              </span>
              <h3 className="mt-4 font-heading text-lg font-medium">{s.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{s.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
