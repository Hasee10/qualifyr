import Link from "next/link";
import { Radar, ShieldCheck, Gauge, UserSearch } from "lucide-react";

/** Split-screen auth chrome: brand panel on the left, form on the right.
 *
 * The panel collapses away below `lg` rather than stacking - on a phone it would push the
 * form below the fold, and the form is the only thing anyone came here for.
 *
 * The curved seam and dotted texture borrow the reference's density; the floating cluster
 * of icon badges stands in for its illustration - there is no illustration asset for this
 * project, and a composition built from the product's own icon language (score, buyer
 * search, decision-maker) says more about Qualifyr than a generic stock illustration would.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-brand p-12 text-brand-foreground lg:flex">
        <div
          aria-hidden
          className="absolute inset-0 opacity-[0.15] [background-image:radial-gradient(currentColor_1px,transparent_1px)] [background-size:20px_20px]"
        />
        {/* Curved seam bulging into the form panel, drawn as an SVG path rather than a
            straight edge - a flat vertical line reads as two unrelated halves. */}
        <svg
          aria-hidden
          className="absolute inset-y-0 -right-px h-full w-16 text-brand"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <path d="M0,0 C60,20 60,80 0,100 L0,0 Z" fill="currentColor" />
        </svg>

        <Link href="/" className="relative flex items-center gap-2 font-semibold">
          <span className="flex size-8 items-center justify-center rounded-lg bg-brand-foreground/15">
            <Radar className="size-4" />
          </span>
          Qualifyr
        </Link>

        <div className="relative max-w-md">
          {/* Floating icon cluster, standing in for an illustration. */}
          <div className="mb-8 flex items-center gap-3">
            <span className="flex size-14 -rotate-6 items-center justify-center rounded-2xl bg-brand-foreground/15 shadow-lg">
              <ShieldCheck className="size-6" />
            </span>
            <span className="flex size-16 items-center justify-center rounded-2xl bg-brand-foreground/20 shadow-lg">
              <Gauge className="size-7" />
            </span>
            <span className="flex size-14 rotate-6 items-center justify-center rounded-2xl bg-brand-foreground/15 shadow-lg">
              <UserSearch className="size-6" />
            </span>
          </div>

          <p className="text-2xl font-semibold leading-snug">
            Few, highly qualified, explainable leads.
          </p>
          <p className="mt-4 text-brand-foreground/80">
            Every company is classified buyer or vendor with evidence, scored 0&ndash;100 with a
            reason you can read, and nothing goes out until you approve it.
          </p>
        </div>

        <p className="relative text-sm text-brand-foreground/70">
          Free to start &mdash; no credit card required.
        </p>
      </aside>

      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2 lg:px-16">
        <div className="mx-auto w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
