/** Desktop + phone frames of the same responsive dashboard - not a separate mobile app.
 *  Caption says so explicitly; do not let this read as app-store marketing. */
export function DeviceMockups() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          One dashboard, every screen
        </h2>
        <p className="mt-4 text-muted-foreground">
          Qualifyr is a responsive web app &mdash; review leads and approve outreach from
          your desk or your phone. There is no separate mobile app.
        </p>
      </div>

      <div className="mt-14 flex flex-col items-center justify-center gap-8 sm:flex-row sm:items-end">
        {/* Desktop frame */}
        <div className="w-full max-w-xl rounded-t-xl border border-border/60 bg-card shadow-xl shadow-black/10 ring-1 ring-black/5">
          <div className="flex items-center gap-1.5 border-b border-border/60 bg-muted/50 px-3 py-2 rounded-t-xl">
            <span className="size-2 rounded-full bg-red-400/70" />
            <span className="size-2 rounded-full bg-amber-400/70" />
            <span className="size-2 rounded-full bg-green-400/70" />
          </div>
          <div className="grid grid-cols-3 gap-2 p-4">
            {["Qualified", "Sent", "Replies"].map((t, i) => (
              <div key={t} className="rounded-lg bg-muted p-3">
                <p className="text-[10px] text-muted-foreground">{t}</p>
                <p className="mt-1 text-base font-semibold">{[42, 118, 9][i]}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Phone frame */}
        <div className="w-40 shrink-0 rounded-[1.75rem] border-4 border-foreground/80 bg-card p-1.5 shadow-xl shadow-black/10">
          <div className="overflow-hidden rounded-[1.1rem] bg-background">
            <div className="mx-auto mt-1.5 h-1 w-10 rounded-full bg-foreground/20" />
            <div className="flex flex-col gap-2 p-3">
              {["Qualified", "Sent", "Replies"].map((t, i) => (
                <div key={t} className="flex items-center justify-between rounded-lg bg-muted px-2.5 py-2">
                  <span className="text-[9px] text-muted-foreground">{t}</span>
                  <span className="text-xs font-semibold">{[42, 118, 9][i]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
