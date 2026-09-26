"use client"

import * as React from "react"
import { Download, Ban, ExternalLink } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, type Lead } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"
import { EmailStatusBadge, ReplyLabelBadge, ReviewButtons, ScoreBadge, StatusBadge, TypeBadge } from "@/components/lead-badges"

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null
  return (
    <div className="grid grid-cols-3 gap-2 py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="col-span-2 break-words">{value}</span>
    </div>
  )
}

function LeadDetail({ leadId, onClose, onChanged }: { leadId: string | null; onClose: () => void; onChanged: () => void }) {
  const [lead, setLead] = React.useState<Lead | null>(null)
  React.useEffect(() => {
    if (!leadId) { setLead(null); return }
    api.lead(leadId).then(setLead).catch(() => setLead(null))
  }, [leadId])

  const suppress = async () => {
    if (!lead || !confirm(`Never contact ${lead.company_name} again?`)) return
    await api.suppress(lead.lead_id, "suppressed from UI")
    onChanged()
    onClose()
  }

  return (
    <Sheet open={!!leadId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{lead?.company_name ?? "…"}</SheetTitle>
        </SheetHeader>
        {lead && (
          <div className="flex flex-col gap-4 p-4 pt-0">
            <div className="flex flex-wrap gap-2">
              <TypeBadge type={lead.company_type} />
              <ScoreBadge score={lead.total_score} />
              <Badge variant="outline">{lead.priority.replace("_", " ")}</Badge>
              {lead.intent_fit !== null && lead.intent_fit !== undefined && (
                <Badge variant={lead.intent_fit ? "default" : "secondary"}>
                  {lead.intent_fit ? "Intent: buyer" : "Intent: no need"}
                  {typeof lead.intent_confidence === "number" ? ` ${Math.round(lead.intent_confidence * 100)}%` : ""}
                </Badge>
              )}
              <StatusBadge status={lead.sequence_status} />
              <ReplyLabelBadge label={lead.reply_label} />
            </div>
            <ReviewButtons leadId={lead.lead_id} verdict={lead.review_verdict} onChange={(v) => setLead({ ...lead, review_verdict: v })} />
            {lead.research_brief && (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Research brief</h3>
                <p className="whitespace-pre-line rounded-lg border bg-muted/40 p-3 text-sm leading-relaxed">{lead.research_brief}</p>
              </section>
            )}
            {lead.intent_signals && lead.intent_signals.length > 0 && (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Intent & requirements</h3>
                {lead.intent_signals.map((s, i) => (
                  <div key={i} className="rounded-lg border p-2 text-sm mb-2">
                    <div className="flex flex-wrap items-center gap-2"><Badge variant="default">{s.kind}</Badge><span className="text-xs text-muted-foreground">{s.source}{s.date ? ` · ${s.date}` : ""}{s.deadline ? ` · closes ${s.deadline}` : ""}</span></div>
                    <div className="mt-1">{s.text}</div>
                    {s.extracted && <div className="mt-1 text-xs text-muted-foreground">{Object.entries(s.extracted).filter(([k]) => k !== "by").map(([k, v]) => `${k}: ${v}`).join(" · ")} <em>({s.extracted.by})</em></div>}
                    {s.source_url && <a className="text-xs underline" href={s.source_url} target="_blank" rel="noreferrer">source</a>}
                  </div>
                ))}
              </section>
            )}
            {lead.reply_excerpt && (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Their reply</h3>
                <p className="rounded-lg bg-muted/50 p-3 text-sm">{lead.reply_excerpt}</p>
                {lead.referred_contact && <Row label="Referred to" value={`${lead.referred_contact.email}${lead.referred_contact.name ? ` (${lead.referred_contact.name})` : ""} — ${lead.referred_contact.status}`} />}
              </section>
            )}
            <section>
              <h3 className="mb-1 text-sm font-semibold">Company</h3>
              <Row label="Website" value={lead.website && <a className="underline" href={lead.website} target="_blank" rel="noreferrer">{lead.domain} <ExternalLink className="inline size-3" /></a>} />
              <Row label="Location" value={[lead.city, lead.country].filter(Boolean).join(", ")} />
              <Row label="Category" value={lead.industry} />
              <Row label="Description" value={lead.company_description} />
              <Row label="Technologies" value={lead.technologies.join(", ")} />
              <Row label="Source" value={lead.source_url ? <a className="underline" href={lead.source_url} target="_blank" rel="noreferrer">{lead.source}</a> : lead.source} />
            </section>
            <section>
              <h3 className="mb-1 text-sm font-semibold">Contact</h3>
              <Row label="Name" value={lead.contact_name} />
              <Row label="Role" value={lead.contact_role} />
              <Row label="Email" value={lead.contact_email && <span>{lead.contact_email} <EmailStatusBadge status={lead.email_status} /></span>} />
              <Row label="Phone" value={lead.phone && <span>{lead.phone}{lead.phone_type && <Badge variant="outline" className="ml-2">{lead.phone_type}</Badge>}</span>} />
              <Row label="Candidate email" value={lead.candidate_email && <span>{lead.candidate_email} <Badge variant="outline">unconfirmed — not sent</Badge></span>} />
              <Row label="Profile" value={lead.linkedin_or_public_profile_url && <a className="underline" href={lead.linkedin_or_public_profile_url} target="_blank" rel="noreferrer">{lead.linkedin_or_public_profile_url}</a>} />
            </section>
            <section>
              <h3 className="mb-1 text-sm font-semibold">Why this score</h3>
              <Row label="Intent" value={lead.intent_reason || null} />
              <Row label="Buyer fit" value={lead.buyer_fit_reason} />
              <Row label="Score" value={lead.score_reason} />
              <Row label="Buying signals" value={lead.buying_signal} />
              <Row label="Pain signals" value={lead.pain_signal} />
              <Row label="Hook" value={lead.personalization_hook} />
              <Row label="Domain age" value={lead.domain_age_years !== null && lead.domain_age_years !== undefined ? `${lead.domain_age_years} years` : null} />
              <Row label="In the news" value={lead.news_mentions && lead.news_mentions.length > 0 ? (
                <ul className="list-disc pl-4">
                  {lead.news_mentions.map((n) => <li key={n.url}><a className="underline" href={n.url} target="_blank" rel="noreferrer">{n.title}</a> <span className="text-muted-foreground">({n.source}, {n.date})</span></li>)}
                </ul>
              ) : null} />
            </section>
            {lead.provenance && Object.keys(lead.provenance).length > 0 && (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Where each field came from</h3>
                {Object.entries(lead.provenance).map(([k, v]) => <Row key={k} label={k.replace(/_/g, " ")} value={v} />)}
              </section>
            )}
            {lead.events && lead.events.length > 0 && (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Activity</h3>
                {lead.events.map((e) => (
                  <div key={e.event_id} className="py-1 text-xs text-muted-foreground">
                    {new Date(e.created_at).toLocaleString()} — {e.event_type}{e.step ? ` (${e.step})` : ""}{e.detail ? `: ${e.detail}` : ""}
                  </div>
                ))}
              </section>
            )}
            <Button variant="destructive" onClick={suppress}><Ban data-icon="inline-start" /> Suppress (never contact)</Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

export default function LeadsPage() {
  const { campaignId } = useCampaign()
  const [leads, setLeads] = React.useState<Lead[]>([])
  const [type, setType] = React.useState<string>("BUYER")
  const [minScore, setMinScore] = React.useState("0")
  const [search, setSearch] = React.useState("")
  const [selected, setSelected] = React.useState<string | null>(null)
  const [page, setPage] = React.useState(1)
  const [downloading, setDownloading] = React.useState(false)
  const pageSize = 25

  const downloadCsv = async () => {
    if (!campaignId) return
    setDownloading(true)
    try {
      // Match the CSV to the current filters: the active type tab (All → every type) and min score.
      await api.downloadExport(campaignId, {
        min_score: Number(minScore) || 0,
        company_type: type === "ALL" ? undefined : type,
      })
    } catch (e) {
      alert(`Download failed: ${(e as Error).message}`)
    } finally {
      setDownloading(false)
    }
  }

  const load = React.useCallback(() => {
    if (!campaignId) return
    api.leads(campaignId, { company_type: type === "ALL" ? undefined : type, min_score: Number(minScore) || 0 })
      .then(setLeads).catch(() => setLeads([]))
  }, [campaignId, type, minScore])
  React.useEffect(() => { load() }, [load])

  const q = search.toLowerCase()
  const visible = leads.filter((l) => !q || l.company_name.toLowerCase().includes(q) || (l.domain ?? "").includes(q) || (l.contact_email ?? "").includes(q))

  const totalPages = Math.max(1, Math.ceil(visible.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const pageItems = visible.slice((safePage - 1) * pageSize, safePage * pageSize)
  const firstShown = visible.length === 0 ? 0 : (safePage - 1) * pageSize + 1
  const lastShown = Math.min(safePage * pageSize, visible.length)

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Leads</h1>
          <p className="text-muted-foreground">Every company processed, with the reason behind its classification and score.</p>
        </div>
        {campaignId && (
          <Button variant="outline" disabled={downloading} onClick={downloadCsv}>
            <Download data-icon="inline-start" /> {downloading ? "Preparing…" : "Download CSV"}
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <Tabs value={type} onValueChange={(v) => { setType(String(v)); setPage(1) }}>
              <TabsList>
                <TabsTrigger value="BUYER">Buyers</TabsTrigger>
                <TabsTrigger value="UNKNOWN">Unknown</TabsTrigger>
                <TabsTrigger value="VENDOR">Vendors</TabsTrigger>
                <TabsTrigger value="ALL">All</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Min score</span>
              <Input className="w-20" value={minScore} onChange={(e) => { setMinScore(e.target.value); setPage(1) }} />
            </div>
            <Input className="max-w-xs" placeholder="Search company, domain, email…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
            <CardDescription className="ml-auto">{visible.length === 0 ? "0 shown" : `${firstShown}–${lastShown} of ${visible.length}`}</CardDescription>
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
                <TableHead>Email</TableHead>
                <TableHead>Sequence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageItems.map((l) => (
                <TableRow key={l.lead_id} className="cursor-pointer" onClick={() => setSelected(l.lead_id)}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{l.company_name}</span>
                      <span className="text-xs text-muted-foreground">{l.domain ?? "no website"} · {l.city}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span>{l.contact_name ?? <span className="text-muted-foreground">—</span>}</span>
                      <span className="text-xs text-muted-foreground">{l.contact_role ?? ""}</span>
                    </div>
                  </TableCell>
                  <TableCell><ScoreBadge score={l.total_score} /></TableCell>
                  <TableCell><TypeBadge type={l.company_type} /></TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <span className="text-xs">{l.contact_email ?? "—"}</span>
                      {l.contact_email && <EmailStatusBadge status={l.email_status} />}
                    </div>
                  </TableCell>
                  <TableCell><StatusBadge status={l.sequence_status} /></TableCell>
                </TableRow>
              ))}
              {visible.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Nothing matches.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <div className="flex items-center justify-between gap-4 border-t pt-4 text-sm">
              <span className="text-muted-foreground">Showing {firstShown}–{lastShown} of {visible.length}</span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>Previous</Button>
                <span className="text-muted-foreground">Page {safePage} of {totalPages}</span>
                <Button variant="outline" size="sm" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <LeadDetail leadId={selected} onClose={() => setSelected(null)} onChanged={load} />
    </div>
  )
}
