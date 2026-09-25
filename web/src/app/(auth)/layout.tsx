import Link from "next/link";
import { Radar } from "lucide-react";

/** Split-screen auth chrome: brand panel on the left, form on the right.
 *
 * The panel collapses away below `lg` rather than stacking - on a phone it would push the
 * form below the fold, and the form is the only thing anyone came here for.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-brand p-12 text-brand-foreground lg:flex">
        <Link href="/" className="relative flex items-center gap-2 font-semibold">
          <span className="flex size-8 items-center justify-center rounded-lg bg-brand-foreground/15">
            <Radar className="size-4" />
          </span>
          Qualifyr
        </Link>

        <div className="relative max-w-md">
          <p className="text-2xl font-semibold leading-snug">
            Few, highly qualified, explainable leads.
          </p>
          <p className="mt-4 text-brand-foreground/80">
            Every company is classified buyer or vendor with evidence, scored 0&ndash;100 with a
            reason you can read, and nothing goes out until you approve it.
          </p>
        </div>

        <p className="relative text-sm text-brand-foreground/70">
          Access is invite-only while the engine is in alpha.
        </p>
      </aside>

      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2 lg:px-16">
        <div className="mx-auto w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
