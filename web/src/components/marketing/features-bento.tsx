import { ShieldCheck, Gauge, UserSearch, Radar, MailCheck, Sheet } from "lucide-react"
import { Card } from "@/components/ui/card"

const features = [
  {
    icon: ShieldCheck,
    title: "Buyer-only classification",
    description: "Vendors and agencies are rejected before they ever reach a score, so the queue is never diluted with companies that sell instead of buy.",
    span: "sm:col-span-2",
  },
  {
    icon: Gauge,
    title: "Explainable 0–100 scoring",
    description: "Every score comes with the plain-English reasons behind it — geography, buyer terms, contact quality, and buying signals.",
    span: "",
  },
  {
    icon: UserSearch,
    title: "Decision-maker discovery",
    description: "Finds a named contact and validates their email before it ever reaches outreach.",
    span: "",
  },
  {
    icon: Radar,
    title: "GTM intelligence signals",
    description: "Hiring, GitHub activity, press and funding mentions — evidence of momentum, not just a static company profile.",
    span: "sm:col-span-2",
  },
  {
    icon: MailCheck,
    title: "Human-approved outreach",
    description: "Every draft is reviewed before it sends. Nothing goes out on a cron.",
    span: "",
  },
  {
    icon: Sheet,
    title: "CSV & Sheets export",
    description: "Every qualified lead, with its full evidence trail, one click away from your own tools.",
    span: "",
  },
]

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

      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => (
          <Card key={f.title} className={`p-6 ${f.span}`}>
            <span className="flex size-10 items-center justify-center rounded-lg bg-brand-muted">
              <f.icon className="size-5 text-brand" />
            </span>
            <h3 className="mt-4 font-heading text-base font-medium">{f.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{f.description}</p>
          </Card>
        ))}
      </div>
    </section>
  )
}
