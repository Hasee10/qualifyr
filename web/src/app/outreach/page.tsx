"use client"

import * as React from "react"
import { Check, X, RotateCcw, Send, RefreshCw, Save } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, STEP_LABEL, type Draft, type Lead, type OutreachEvent, type Queue, type QueueItem, type SendReport } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"
import { ScoreBadge, StatusBadge } from "@/components/lead-badges"
import { cn } from "@/lib/utils"

function DraftBadge({ status }: { status: Draft["status"] }) {
  const variant = status === "approved" ? "default" : status === "rejected" ? "destructive" : status === "sent" ? "secondary" : "outline"
  return <Badge variant={variant}>{status}</Badge>
}

function Editor({ item, onChange }: { item: QueueItem; onChange: (d: Draft) => void }) {
  const [subject, setSubject] = React.useState(item.draft.subject)
  const [body, setBody] = React.useState(item.draft.body)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const dirty = subject !== item.draft.subject || body !== item.draft.body

  React.useEffect(() => { setSubject(item.draft.subject); setBody(item.draft.body); setError(null) }, [item])

  const run = async (label: string, fn: () => Promise<Draft>) => {
    setBusy(label); setError(null)
    try { onChange(await fn()) } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }
  const save = () => run("save", () => api.saveDraft(item.lead.lead_id, item.step, subject, body))
  const approve = () => run("approve", async () => {
    if (dirty) await api.saveDraft(item.lead.lead_id, item.step, subject, body)
    return api.approve(item.lead.lead_id, item.step)
  })
  const reject = () => run("reject", () => api.reject(item.lead.lead_id, item.step))
  const reset = () => run("reset", () => api.resetDraft(item.lead.lead_id, item.step))
  const locked = item.draft.status === "sent"
  const { lead } = item

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">{lead.company_name} <ScoreBadge score={lead.total_score} /></CardTitle>
            <CardDescription>
              {STEP_LABEL[item.step]} → {lead.contact_name ? `${lead.contact_name} (${lead.contact_role}) ` : ""}<span className="font-mono">{lead.contact_email}</span>
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <DraftBadge status={item.draft.status} />
            {item.draft.edited === 1 && <Badge variant="outline">edited</Badge>}
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
          <div><span className="font-medium text-foreground">Why a buyer:</span> {lead.buyer_fit_reason}</div>
          {lead.personalization_hook && <div><span className="font-medium text-foreground">Observed facts:</span> {lead.personalization_hook}</div>}
          {lead.website && <div><span className="font-medium text-foreground">Website:</span> <a className="underline" href={lead.website} target="_blank" rel="noreferrer">{lead.website}</a></div>}
        </div>
        <div className="grid gap-1">
          <label className="text-xs text-muted-foreground">Subject</label>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={locked} />
        </div>
        <div className="grid gap-1">
          <label className="text-xs text-muted-foreground">Body (plain text, sent exactly as shown)</label>
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={18} className="font-mono text-[13px]" disabled={locked} />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <Button onClick={approve} disabled={locked || !!busy}><Check data-icon="inline-start" /> {dirty ? "Save & approve" : "Approve"}</Button>
          <Button variant="outline" onClick={save} disabled={locked || !dirty || !!busy}><Save data-icon="inline-start" /> Save edits</Button>
          <Button variant="outline" onClick={reset} disabled={locked || !!busy}><RotateCcw data-icon="inline-start" /> Re-render from template</Button>
          <Button variant="destructive" onClick={reject} disabled={locked || !!busy} className="ml-auto"><X data-icon="inline-start" /> Reject (skip this email)</Button>
        </div>
      </CardContent>
    </Card>
  )
}

function SendPanel({ campaignId, queue, onDone }: { campaignId: string; queue: Queue; onDone: () => void }) {
  const [limit, setLimit] = React.useState("10")
  const [ignoreWindow, setIgnoreWindow] = React.useState(false)
  const [report, setReport] = React.useState<SendReport | null>(null)
  const [busy, setBusy] = React.useState(false)
  const approved = queue.items.filter((i) => i.draft.status === "approved").length

  const send = async (dry: boolean) => {
    if (!dry && !confirm(`Send up to ${limit} approved email(s) from your Gmail now?`)) return
    setBusy(true); setReport(null)
    try {
      setReport(await api.send(campaignId, { limit: Number(limit) || undefined, dry_run: dry, ignore_window: ignoreWindow }))
      onDone()
    } catch (e) {
      setReport({ sent: 0, skipped: 0, failed: 1, stopped_reason: (e as Error).message, details: [], mode: "error", sync: null })
    } finally { setBusy(false) }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Send approved</CardTitle>
        <CardDescription>
          {approved} approved and due · {queue.sent_today}/{queue.daily_limit} sent today ·{" "}
          {queue.smtp_configured ? "Gmail configured" : "no credentials: sends are dry runs"}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Max this batch</span>
          <Input className="w-20" value={limit} onChange={(e) => setLimit(e.target.value)} />
          <label className="flex items-center gap-1 text-sm text-muted-foreground">
            <input type="checkbox" checked={ignoreWindow} onChange={(e) => setIgnoreWindow(e.target.checked)} /> send outside 09–18 PKT
          </label>
          <Button onClick={() => send(false)} disabled={busy || approved === 0}><Send data-icon="inline-start" /> Send now</Button>
          <Button variant="outline" onClick={() => send(true)} disabled={busy || approved === 0}>Dry run</Button>
        </div>
        {report && (
          <div className="rounded-lg border p-3 text-sm">
            <div className="font-medium">
              {report.mode}: sent {report.sent}, held {report.skipped}, failed {report.failed}
              {report.stopped_reason && <span className="text-muted-foreground"> — {report.stopped_reason}</span>}
            </div>
            {report.sync && <div className="text-xs text-muted-foreground">inbox sync: {JSON.stringify(report.sync)}</div>}
            {report.details.map((d, i) => <div key={i} className="text-xs text-muted-foreground">{d}</div>)}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function OutreachPage() {
  const { campaignId } = useCampaign()
  const [queue, setQueue] = React.useState<Queue | null>(null)
  const [selected, setSelected] = React.useState<number>(0)
  const [tab, setTab] = React.useState("review")
  const [sequence, setSequence] = React.useState<Lead[]>([])
  const [activity, setActivity] = React.useState<OutreachEvent[]>([])
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    if (!campaignId) return
    try {
      const [q, s, a] = await Promise.all([api.queue(campaignId), api.sequence(campaignId), api.activity(campaignId)])
      setQueue(q); setSequence(s); setActivity(a); setError(null)
    } catch (e) { setError((e as Error).message) }
  }, [campaignId])
  React.useEffect(() => { load() }, [load])

  const updateDraft = (d: Draft) => {
    setQueue((q) => q && { ...q, items: q.items.map((i) => i.lead.lead_id === d.lead_id && i.step === d.step ? { ...i, draft: d } : i) })
  }

  const items = queue?.items ?? []
  const current = items[selected] ?? items[0]
  const pending = items.filter((i) => i.draft.status === "pending").length

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Outreach</h1>
          <p className="text-muted-foreground">Every email is previewed here and sent only after you approve it. Follow-ups come back for approval on their own day.</p>
        </div>
        <Button variant="outline" onClick={load}><RefreshCw data-icon="inline-start" /> Refresh</Button>
      </div>
      {error && <p className="text-sm text-destructive">API error: {error}</p>}

      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <TabsList>
          <TabsTrigger value="review">Review queue {items.length > 0 && <Badge variant="secondary" className="ml-1">{pending}</Badge>}</TabsTrigger>
          <TabsTrigger value="sequence">In sequence ({sequence.length})</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "review" && queue && (
        <div className="grid gap-6">
          <SendPanel campaignId={campaignId!} queue={queue} onDone={load} />
          {items.length === 0 ? (
            <Card><CardContent className="py-10 text-center text-muted-foreground">Nothing is due. Leads become due after discovery (Email 1) and 3 / 4 days after each send.</CardContent></Card>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[minmax(260px,1fr)_2fr]">
              <Card>
                <CardHeader><CardTitle>Due now ({items.length})</CardTitle></CardHeader>
                <CardContent className="p-0">
                  {items.map((i, idx) => (
                    <button
                      key={`${i.lead.lead_id}-${i.step}`}
                      onClick={() => setSelected(idx)}
                      className={cn("flex w-full flex-col items-start gap-0.5 border-t px-4 py-3 text-left text-sm hover:bg-muted", current === i && "bg-muted")}
                    >
                      <span className="flex w-full items-center justify-between gap-2">
                        <span className="font-medium">{i.lead.company_name}</span>
                        <DraftBadge status={i.draft.status} />
                      </span>
                      <span className="text-xs text-muted-foreground">{STEP_LABEL[i.step]} · {i.lead.contact_email}</span>
                    </button>
                  ))}
                </CardContent>
              </Card>
              {current && <Editor item={current} onChange={updateDraft} />}
            </div>
          )}
        </div>
      )}

      {tab === "sequence" && (
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead><TableHead>Email</TableHead><TableHead>Status</TableHead>
                  <TableHead>Email 1</TableHead><TableHead>Follow-up 1</TableHead><TableHead>Follow-up 2</TableHead><TableHead>Next</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sequence.map((l) => (
                  <TableRow key={l.lead_id}>
                    <TableCell className="font-medium">{l.company_name}</TableCell>
                    <TableCell className="text-xs">{l.contact_email}</TableCell>
                    <TableCell><StatusBadge status={l.sequence_status} />{l.reply_status && <div className="text-xs text-muted-foreground">{l.reply_status}</div>}</TableCell>
                    <TableCell className="text-xs">{l.email_1_sent_at ? new Date(l.email_1_sent_at).toLocaleDateString() : "—"}</TableCell>
                    <TableCell className="text-xs">{l.followup_1_at ? new Date(l.followup_1_at).toLocaleDateString() : "—"}</TableCell>
                    <TableCell className="text-xs">{l.followup_2_at ? new Date(l.followup_2_at).toLocaleDateString() : "—"}</TableCell>
                    <TableCell className="text-xs">{l.next_contact_at ? new Date(l.next_contact_at).toLocaleDateString() : "—"}</TableCell>
                  </TableRow>
                ))}
                {sequence.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No one in sequence yet.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {tab === "activity" && (
        <Card>
          <CardContent className="pt-6">
            {activity.length === 0 && <p className="text-center text-muted-foreground">No activity yet.</p>}
            {activity.map((e) => (
              <div key={e.event_id} className="flex flex-wrap gap-2 border-t py-2 text-sm first:border-t-0">
                <span className="w-40 text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString()}</span>
                <Badge variant={e.event_type === "sent" ? "default" : e.event_type === "bounced" || e.event_type === "send_failed" ? "destructive" : "outline"}>{e.event_type}</Badge>
                <span className="font-medium">{e.company_name}</span>
                <span className="text-xs text-muted-foreground">{e.step ?? ""} {e.detail ?? ""}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
