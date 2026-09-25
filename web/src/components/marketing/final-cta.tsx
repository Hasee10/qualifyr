import Link from "next/link"
import { Button } from "@/components/ui/button"

/** The brand accent is strict black/white, so a `bg-brand` band flips to a full white slab
 *  in dark mode - jarring against an otherwise black page. Instead this is a dark, elevated
 *  panel that belongs to the page, with the button carrying the accent (same treatment as
 *  the nav CTA). Works in both themes: the panel tracks the surface, the button inverts. */
export function FinalCta() {
  return (
    <section className="px-4 py-20 sm:px-6">
      <div className="relative mx-auto max-w-4xl overflow-hidden rounded-3xl border border-border/60 bg-card px-6 py-16 text-center shadow-2xl shadow-black/20">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-24 h-48 opacity-60 blur-3xl"
          style={{ background: "radial-gradient(50% 60% at 50% 0%, var(--brand-muted), transparent 70%)" }}
        />
        <h2 className="relative text-3xl font-semibold tracking-tight sm:text-4xl">
          Stop guessing who to reach out to
        </h2>
        <p className="relative mt-4 text-muted-foreground">
          Create your account and start qualifying leads in minutes.
        </p>
        <div className="relative mt-8">
          <Button
            size="lg"
            nativeButton={false}
            className="bg-brand text-brand-foreground hover:bg-brand/90"
            render={<Link href="/sign-up" />}
          >
            Get started free
          </Button>
        </div>
      </div>
    </section>
  )
}
