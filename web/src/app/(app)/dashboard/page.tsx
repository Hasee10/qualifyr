"use client"

import * as React from "react"
import Link from "next/link"
import { Users, ShieldCheck, Send, MessageSquareReply, Target, Gauge } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { api, type Lead, type Stats } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"
import { ScoreBadge, StatusBadge, TypeBadge } from "@/components/lead-badges"

function StatCard({ title, value, hint, icon: Icon, highlight }: { title: string; value: string | number; hint: string; icon: React.ElementType; highlight?: boolean }) {
  return (
    <Card className={highlight ? "border-brand/40 bg-brand-muted/30" : undefined}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-muted-foreground">{title}</span>
          <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${highlight ? "bg-brand-muted text-brand" : "bg-muted text-muted-foreground"}`}>
            <Icon className="size-4" />
          </span>
        </div>
        <div className="mt-3 text-3xl font-semibold tracking-tight tabular-nums">{value}</div>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  )
}

const chartConfig = {
  count: { label: "Leads", theme: { light: "var(--chart-1)", dark: "var(--chart-1)" } },
}

export default function DashboardPage() {
  const { campaignId, campaigns } = useCampaign()
  const [stats, setStats] = React.useState<Stats | null>(null)
  const [top, setTop] = React.useState<Lead[]>([])

  React.useEffect(() => {
    if (!campaignId) return
    api.stats(campaignId).then(setStats).catch(() => setStats(null))
    api.leads(campaignId, { company_type: "BUYER" }).then((l) => setTop(l.slice(0, 8))).catch(() => setTop([]))
  }, [campaignId])

  const campaign = campaigns.find((c) => c.campaign_id === campaignId)
  if (!campaignId) {
    return <p className="text-muted-foreground">No campaigns found. Add a YAML under <code>config/campaigns/</code>.</p>
  }

  const bands = stats ? Object.entries(stats.score_bands).map(([band, count]) => ({ band, count })) : []

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-bold">{campaign?.name ?? campaignId}</h1>
        <p className="text-muted-foreground">{campaign?.offer}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {stats ? (
          <>
            <StatCard title="Reviewer accuracy" value={stats.accuracy === null ? "—" : `${Math.round(stats.accuracy * 100)}%`} hint={stats.reviewed ? `${stats.correct}/${stats.reviewed} marked correct · target 80%` : "mark leads correct / wrong in the queue"} icon={Gauge} />
            <StatCard title="With intent" value={stats.with_intent} hint="tenders, RFQs or hiring that imply a purchase" icon={Target} />
            <StatCard title="Companies processed" value={stats.leads} hint={`${stats.by_type.BUYER} buyers · ${stats.by_type.VENDOR} vendors · ${stats.by_type.UNKNOWN} unknown`} icon={Users} />
            <StatCard title="Qualified buyers" value={stats.qualified} hint={`score ≥ ${campaign?.min_score ?? 70}, ${stats.outreach_ready} with a validated email`} icon={ShieldCheck} highlight />
            <StatCard title="Emails sent" value={stats.emails_sent} hint={`${stats.by_status.email_1_sent} in step 1 · ${stats.by_status.followup_1_sent} in step 2 · ${stats.by_status.followup_2_sent} done`} icon={Send} />
            <StatCard title="Replies" value={stats.replied} hint={`${stats.bounced} bounced · ${stats.by_status.unsubscribed} unsubscribed`} icon={MessageSquareReply} />
          </>
        ) : (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28" />)
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Score distribution</CardTitle>
            <CardDescription>70+ is outreach-eligible; 50–69 goes to review</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[220px] w-full">
              <BarChart data={bands}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="band" className="text-xs" />
                <YAxis allowDecimals={false} className="text-xs" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="count" fill="var(--color-count)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Top buyers</CardTitle>
                <CardDescription>Highest-scoring BUYER companies</CardDescription>
              </div>
              <Link href="/leads"><Button variant="outline" size="sm">All leads</Button></Link>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Sequence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {top.map((l) => (
                  <TableRow key={l.lead_id}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">{l.company_name}</span>
                        <span className="text-xs text-muted-foreground">{l.domain ?? "no website"} · {l.city}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span>{l.contact_name ?? <span className="text-muted-foreground">no named contact</span>}</span>
                        <span className="text-xs text-muted-foreground">{l.contact_email ?? "—"}</span>
                      </div>
                    </TableCell>
                    <TableCell><ScoreBadge score={l.total_score} /></TableCell>
                    <TableCell><TypeBadge type={l.company_type} /></TableCell>
                    <TableCell><StatusBadge status={l.sequence_status} /></TableCell>
                  </TableRow>
                ))}
                {top.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">No buyers yet — run the campaign.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
