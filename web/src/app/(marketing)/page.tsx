import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Placeholder. Phase 3 replaces this with the real sections (hero + product slideshow,
 *  source marquee, features bento, how it works, device mockups, FAQ, closing CTA). */
export default function LandingPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-24 text-center sm:px-6">
      <h1 className="mx-auto max-w-3xl text-5xl font-semibold tracking-tight sm:text-6xl">
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
    </section>
  );
}
