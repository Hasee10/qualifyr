import { ShieldCheck, Gauge, UserSearch, Radar, MailCheck, Sheet } from "lucide-react"
import { Card } from "@/components/ui/card"

function FeatureCard({
  icon: Icon,
  title,
  description,
  lead = false,
}: {
  icon: React.ElementType
  title: string
  description: string
  lead?: boolean
}) {
  return (
    <Card className={lead ? "gap-3 p-8" : "gap-2 p-6"}>
      <span className={`flex items-center justify-center rounded-lg bg-brand-muted ${lead ? "size-12" : "size-10"}`}>
        <Icon className={lead ? "size-6 text-brand" : "size-5 text-brand"} />
      </span>
      <h3 className={`font-heading font-medium ${lead ? "mt-2 text-lg" : "mt-4 text-base"}`}>{title}</h3>
      <p className={`text-muted-foreground ${lead ? "max-w-xl text-sm" : "text-sm"}`}>{description}</p>
    </Card>
  )
}

/** Asymmetric, not a uniform grid: one lead card states the core claim, paired cards work
 *  through the supporting pieces, a closing full-width card lands on "what you walk away
 *  with." A grid of six identical boxes reads as a spec sheet; this reads as an argument. */
export function FeaturesBento() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Everything between &ldquo;a list of companies&rdquo; and a booked meeting
        </h2>
        <p className="mt-4 text-muted-foreground">
          Discovery, qualification, contact discovery and outreach in one pipeline &mdash;
          each step keeps its evidence.
        </p>
      </div>

      <div className="mt-14 flex flex-col gap-4">
        <FeatureCard
          lead
          icon={ShieldCheck}
          title="Buyer-only classification"
          description="Vendors and agencies are rejected before they ever reach a score, so the queue is never diluted with companies that sell instead of buy."
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <FeatureCard
            icon={Gauge}
            title="Explainable 0–100 scoring"
            description="Every score comes with the plain-English reasons behind it — geography, buyer terms, contact quality, and buying signals."
          />
          <FeatureCard
            icon={UserSearch}
            title="Decision-maker discovery"
            description="Finds a named contact and validates their email before it ever reaches outreach."
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FeatureCard
            icon={Radar}
            title="GTM intelligence signals"
            description="Hiring, GitHub activity, press and funding mentions — evidence of momentum, not just a static company profile."
          />
          <FeatureCard
            icon={MailCheck}
            title="Human-approved outreach"
            description="Every draft is reviewed before it sends. Nothing goes out on a cron."
          />
        </div>

        <FeatureCard
          lead
          icon={Sheet}
          title="CSV & Sheets export"
          description="Every qualified lead, with its full evidence trail, one click away from your own tools."
        />
      </div>
    </section>
  )
}
