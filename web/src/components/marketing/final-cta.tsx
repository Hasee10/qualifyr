import Link from "next/link"
import { Button } from "@/components/ui/button"

export function FinalCta() {
  return (
    <section className="bg-brand py-20">
      <div className="mx-auto max-w-2xl px-4 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-brand-foreground sm:text-4xl">
          Stop guessing who to reach out to
        </h2>
        <p className="mt-4 text-brand-foreground/80">
          Create your account and start qualifying leads in minutes.
        </p>
        <div className="mt-8">
          <Button
            size="lg"
            nativeButton={false}
            className="bg-brand-foreground text-brand hover:bg-brand-foreground/90"
            render={<Link href="/sign-up" />}
          >
            Get started free
          </Button>
        </div>
      </div>
    </section>
  )
}
