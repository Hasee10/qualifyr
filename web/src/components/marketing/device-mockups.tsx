function PhoneFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-40 shrink-0 rounded-[1.75rem] border-4 border-foreground/80 bg-card p-1.5 shadow-xl shadow-black/10">
      <div className="overflow-hidden rounded-[1.1rem] bg-background">
        <div className="mx-auto mt-1.5 h-1 w-10 rounded-full bg-foreground/20" />
        {children}
      </div>
    </div>
  )
}

const panels = [
  {
    title: "Approve outreach on your phone",
    description: "Review a drafted email and approve it the moment it's ready, wherever you are.",
    frame: (
      <div className="flex flex-col gap-2 p-3">
        <div className="rounded-lg bg-muted px-2.5 py-2 text-[9px] text-muted-foreground">
          Hi Sana, saw the Series A news for Ittefaq...
        </div>
        <div className="flex items-center justify-between rounded-lg bg-brand px-2.5 py-1.5">
          <span className="text-[9px] font-medium text-brand-foreground">Approve &amp; send</span>
        </div>
      </div>
    ),
  },
  {
    title: "The full lead dashboard",
    description: "Score bands, top buyers and every campaign's status in one place.",
    frame: (
      <div className="flex flex-col gap-2 p-3">
        {["Qualified", "Sent", "Replies"].map((t, i) => (
          <div key={t} className="flex items-center justify-between rounded-lg bg-muted px-2.5 py-2">
            <span className="text-[9px] text-muted-foreground">{t}</span>
            <span className="text-xs font-semibold">{[42, 118, 9][i]}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    title: "Every score, explained",
    description: "See exactly why a lead scored what it did, down to the individual reason.",
    frame: (
      <div className="flex flex-col gap-2 p-3">
        <div className="flex items-center justify-between rounded-lg bg-muted px-2.5 py-2">
          <span className="text-[9px]">RBS Interiors</span>
          <span className="rounded-full bg-brand-muted px-1.5 py-0.5 text-[9px] font-medium text-brand">84</span>
        </div>
        <div className="rounded-lg bg-muted px-2.5 py-2 text-[8px] text-muted-foreground">
          + in target city · + decision-maker found · + open growth role
        </div>
      </div>
    ),
  },
]

/** Same panel density as the reference's "see it in action" gallery, reframed around a
 *  responsive web app rather than a native mobile app - the caption says so explicitly so
 *  this never reads as app-store marketing. */
export function DeviceMockups() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">See it in action</h2>
        <p className="mt-4 text-muted-foreground">
          The same responsive dashboard on your desk or in your pocket &mdash; there is no
          separate mobile app.
        </p>
      </div>

      <div className="mt-14 grid gap-10 sm:grid-cols-3">
        {panels.map((p) => (
          <div key={p.title} className="text-center">
            <PhoneFrame>{p.frame}</PhoneFrame>
            <h3 className="mt-6 font-heading text-base font-medium">{p.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{p.description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
