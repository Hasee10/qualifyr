import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ProductSlideshow } from "@/components/marketing/product-slideshow"

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-20 pb-16 sm:pt-28">
      {/* Soft brand glow behind the headline only - never a full-bleed surface. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[480px] bg-[radial-gradient(ellipse_60%_50%_at_50%_0%,var(--brand-muted),transparent)]"
      />

      <div className="mx-auto max-w-6xl px-4 text-center sm:px-6">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
          Buyer-only lead engine for Pakistan &amp; the GCC
        </span>

        <h1 className="mx-auto mt-6 max-w-3xl text-5xl font-semibold tracking-tight sm:text-6xl">
          See who actually <span className="text-brand">buys</span>. Not just who exists.
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Qualifyr discovers companies from free public sources, rejects the agencies and
          vendors, finds a decision-maker, and scores every lead 0&ndash;100 with a reason you
          can read.
        </p>

        <div className="mt-10 flex items-center justify-center gap-3">
          <Button
            size="lg"
            nativeButton={false}
            className="bg-brand text-brand-foreground hover:bg-brand/90"
            render={<a href="mailto:ihaseebarshad10@gmail.com?subject=Qualifyr%20access" />}
          >
            Request access
          </Button>
          <Button size="lg" variant="outline" nativeButton={false} render={<Link href="/sign-in" />}>
            Sign in
          </Button>
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          No self-serve signup &mdash; every account is provisioned by hand.
        </p>
      </div>

      <div className="mx-auto mt-16 max-w-6xl px-4 sm:px-6">
        <ProductSlideshow />
      </div>
    </section>
  )
}
