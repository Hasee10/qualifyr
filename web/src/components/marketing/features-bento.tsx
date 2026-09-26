import { ShieldCheck, Gauge, UserSearch, Radar, MailCheck, Sheet } from "lucide-react"
import { cn } from "@/lib/utils"
import { Illustration } from "@/components/marketing/illustration"

function FeatureCard({
  icon: Icon,
  title,
  description,
  className,
}: {
  icon: React.ElementType
  title: string
  description: string
  className?: string
}) {
  return (
    <div
      className={cn(
        "group flex flex-col rounded-2xl border border-border/60 bg-card p-5 transition-colors hover:border-border hover:bg-muted/40",
        className
      )}
    >
      <span className="flex size-9 items-center justify-center rounded-xl bg-brand-muted transition-colors group-hover:bg-brand/15">
        <Icon className="size-[18px] text-brand" />
      </span>
      <h3 className="mt-4 font-heading text-[15px] font-medium">{title}</h3>
      <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

/** Bento, not a uniform grid: six features on a three-column grid where the wide card
 *  alternates side each row (2-1 / 1-2 / 2-1). Every row is full, so there is no dead
 *  space, and the asymmetry reads as an argument rather than a spec sheet. */
export function FeaturesBento() {
  return (
    <section id="features" className="mx-auto max-w-5xl px-4 py-16 sm:px-6 sm:py-20">
      <div className="grid items-center gap-8 lg:grid-cols-[1fr_1.1fr] lg:gap-14">
        <Illustration
          src="/brand/feature-qualification-funnel.png"
          alt="Companies narrowing through a qualification funnel into scored buyers"
          width={1448}
          height={1086}
          className="mx-auto aspect-[4/3] w-full max-w-sm lg:order-first"
        />
        <div className="text-center lg:text-left">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Everything between &ldquo;a list of companies&rdquo; and a booked meeting
          </h2>
          <p className="mt-4 text-muted-foreground">
            Discovery, qualification, contact discovery and outreach in one pipeline &mdash;
            each step keeps its evidence.
          </p>
        </div>
      </div>

      <div className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <FeatureCard
          className="lg:col-span-2"
          icon={ShieldCheck}
          title="Buyer-only classification"
          description="Vendors and agencies are rejected before they ever reach a score, so the queue is never diluted with companies that sell instead of buy."
        />
        <FeatureCard
          icon={Gauge}
          title="Explainable 0–100 scoring"
          description="Every score comes with the plain-English reasons behind it — geography, buyer terms, contact quality, buying signals."
        />

        <FeatureCard
          icon={UserSearch}
          title="Decision-maker discovery"
          description="Finds a named contact and validates their email before it ever reaches outreach."
        />
        <FeatureCard
          className="lg:col-span-2"
          icon={Radar}
          title="GTM intelligence signals"
          description="Hiring, GitHub activity, press and funding mentions — evidence of momentum, not just a static company profile."
        />

        <FeatureCard
          className="lg:col-span-2"
          icon={MailCheck}
          title="Human-approved outreach"
          description="Every draft is reviewed before it sends. Nothing goes out on a cron, and nothing leaves without a person behind it."
        />
        <FeatureCard
          icon={Sheet}
          title="CSV & Sheets export"
          description="Every qualified lead, with its full evidence trail, one click from your own tools."
        />
      </div>
    </section>
  )
}
