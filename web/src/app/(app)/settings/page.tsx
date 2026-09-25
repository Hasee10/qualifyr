"use client"

import * as React from "react"
import { Ban, Trash2, Save, CheckCircle2, FileSpreadsheet, Plus } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, type MailboxState, type Suppression } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"
import { cn } from "@/lib/utils"

const NEW_CAMPAIGN_TEMPLATE = `campaign_id: my-campaign-001
name: My first campaign
offer: What you sell, in one sentence (used inside every email)

target_industries: [retail, clothing]
geography:
  countries: [Pakistan]
  cities: [Lahore]
target_roles: [founder, owner, ceo, director]
buyer_keywords: [retailer, store, brand, shop, outlet]
negative_keywords: []

overture_categories: [clothing, shoe_store, supermarket]
osm_categories: [shop=clothes, shop=shoes]
chamber_sources: []        # [kcci] when Karachi is in cities
chamber_name_keywords: []

min_score: 70
max_companies: 60
max_pages_per_site: 6
exclude_chains: false
`

function Suppressions() {
  const [rows, setRows] = React.useState<Suppression[]>([])
  const [value, setValue] = React.useState("")
  const [reason, setReason] = React.useState("")
  const load = React.useCallback(() => { api.suppressions().then(setRows).catch(() => setRows([])) }, [])
  React.useEffect(() => { load() }, [load])
  const add = async () => {
    if (!value.trim()) return
    await api.addSuppression(value.trim(), reason.trim() || undefined)
    setValue(""); setReason(""); load()
  }
  const remove = async (v: string) => {
    if (!confirm(`Allow contacting ${v} again?`)) return
    await api.removeSuppression(v); load()
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Suppression list</CardTitle>
        <CardDescription>Addresses and domains that are never emailed. Bounces, unsubscribes and "not interested" replies land here automatically.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input className="max-w-xs" placeholder="email or domain" value={value} onChange={(e) => setValue(e.target.value)} />
          <Input className="max-w-xs" placeholder="reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button onClick={add}><Ban data-icon="inline-start" /> Suppress</Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow><TableHead>Value</TableHead><TableHead>Kind</TableHead><TableHead>Reason</TableHead><TableHead>Added</TableHead><TableHead /></TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.value}>
                <TableCell className="font-mono text-xs">{r.value}</TableCell>
                <TableCell><Badge variant="outline">{r.kind}</Badge></TableCell>
                <TableCell className="text-xs text-muted-foreground">{r.reason ?? ""}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</TableCell>
                <TableCell><Button size="icon-xs" variant="ghost" onClick={() => remove(r.value)}><Trash2 /></Button></TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Nothing suppressed.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function Mailboxes({ campaignId }: { campaignId: string | null }) {
  const [rows, setRows] = React.useState<MailboxState[]>([])
  React.useEffect(() => { api.mailboxes(campaignId ?? undefined).then(setRows).catch(() => setRows([])) }, [campaignId])
  return (
    <Card>
      <CardHeader>
        <CardTitle>Mailboxes</CardTitle>
        <CardDescription>Configured through environment secrets (<code>GTM_SMTP_*</code>, <code>GTM_MAILBOX_N_*</code>). Each has its own cap, warm-up and bounce guard.</CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? <p className="text-sm text-muted-foreground">No mailboxes configured in this environment — sends are dry runs.</p> : (
          <Table>
            <TableHeader>
              <TableRow><TableHead>Address</TableHead><TableHead>Auth</TableHead><TableHead>Today</TableHead><TableHead>Warm-up</TableHead><TableHead>Bounced</TableHead><TableHead>State</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((m) => (
                <TableRow key={m.address} className={cn(m.paused_reason && "bg-destructive/5")}>
                  <TableCell className="font-mono text-xs">{m.address}</TableCell>
                  <TableCell><Badge variant="outline">{m.auth_mode}</Badge></TableCell>
                  <TableCell>{m.sent_today}/{m.cap}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{m.days_active ? `day ${m.days_active}` : "never sent"}</TableCell>
                  <TableCell>{m.bounced_today}</TableCell>
                  <TableCell>{m.paused_reason ? <Badge variant="destructive">{m.paused_reason}</Badge> : <Badge>{m.remaining} left</Badge>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function CampaignEditor() {
  const { campaigns, campaignId, refresh } = useCampaign()
  const [selected, setSelected] = React.useState<string | "new">(campaignId ?? "new")
  const [text, setText] = React.useState("")
  const [status, setStatus] = React.useState<{ ok: boolean; message: string } | null>(null)
  const [busy, setBusy] = React.useState(false)

  React.useEffect(() => {
    setStatus(null)
    if (selected === "new") { setText(NEW_CAMPAIGN_TEMPLATE); return }
    api.campaignYaml(selected).then((r) => setText(r.yaml)).catch((e) => setStatus({ ok: false, message: (e as Error).message }))
  }, [selected])

  const validate = async () => {
    setBusy(true)
    try {
      const r = await api.validateCampaign(text)
      setStatus(r.ok ? { ok: true, message: `Valid: ${r.name} (${r.campaign_id}) — sources: ${r.sources.join(", ") || "none!"}` } : { ok: false, message: r.error ?? "invalid" })
    } finally { setBusy(false) }
  }
  const save = async () => {
    setBusy(true)
    try {
      const v = await api.validateCampaign(text)
      if (!v.ok) { setStatus({ ok: false, message: v.error ?? "invalid" }); return }
      const r = await api.saveCampaignYaml(v.campaign_id, text)
      setStatus({ ok: true, message: `Saved ${r.file}` })
      await refresh()
      setSelected(v.campaign_id)
    } catch (e) { setStatus({ ok: false, message: (e as Error).message }) } finally { setBusy(false) }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle>Campaign editor</CardTitle>
            <CardDescription>Edit <code>config/campaigns/*.yaml</code> here. Validation runs the same schema the engine uses.</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <select className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm" value={selected} onChange={(e) => setSelected(e.target.value)}>
              {campaigns.map((c) => <option key={c.campaign_id} value={c.campaign_id}>{c.name}</option>)}
              <option value="new">+ New campaign</option>
            </select>
            {selected !== "new" && <Button variant="outline" size="sm" onClick={() => setSelected("new")}><Plus data-icon="inline-start" /> New</Button>}
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={26} className="font-mono text-[13px]" spellCheck={false} />
        {status && <p className={cn("text-sm", status.ok ? "text-green-600 dark:text-green-400" : "text-destructive")}>{status.message}</p>}
        <div className="flex gap-2">
          <Button variant="outline" onClick={validate} disabled={busy}><CheckCircle2 data-icon="inline-start" /> Validate</Button>
          <Button onClick={save} disabled={busy}><Save data-icon="inline-start" /> Save</Button>
        </div>
      </CardContent>
    </Card>
  )
}

function Sheets({ campaignId }: { campaignId: string | null }) {
  const [status, setStatus] = React.useState<{ configured: boolean; spreadsheet_id: string | null } | null>(null)
  const [result, setResult] = React.useState<string | null>(null)
  React.useEffect(() => { api.sheetsStatus().then(setStatus).catch(() => setStatus(null)) }, [])
  const run = async () => {
    if (!campaignId) return
    setResult("Exporting…")
    try { const r = await api.exportSheets(campaignId); setResult(`Wrote ${r.rows} leads to tab "${r.tab}" — ${r.url}`) }
    catch (e) { setResult((e as Error).message) }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Google Sheets mirror</CardTitle>
        <CardDescription>One-way copy of qualified leads for people who won&apos;t open this UI. Needs <code>GTM_SHEETS_CREDENTIALS_JSON</code> and <code>GTM_SHEETS_SPREADSHEET_ID</code>.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3">
        {status?.configured ? <Badge>configured</Badge> : <Badge variant="outline">not configured</Badge>}
        <Button onClick={run} disabled={!status?.configured || !campaignId}><FileSpreadsheet data-icon="inline-start" /> Export qualified leads</Button>
        {result && <span className="text-sm text-muted-foreground">{result}</span>}
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  const { campaignId } = useCampaign()
  const [tab, setTab] = React.useState("campaigns")
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Campaign files, mailboxes, suppression list and exports.</p>
      </div>
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <TabsList>
          <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          <TabsTrigger value="mailboxes">Mailboxes</TabsTrigger>
          <TabsTrigger value="suppressions">Suppressions</TabsTrigger>
          <TabsTrigger value="sheets">Google Sheets</TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === "campaigns" && <CampaignEditor />}
      {tab === "mailboxes" && <Mailboxes campaignId={campaignId} />}
      {tab === "suppressions" && <Suppressions />}
      {tab === "sheets" && <Sheets campaignId={campaignId} />}
    </div>
  )
}
