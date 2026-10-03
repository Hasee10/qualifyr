"use client"

import * as React from "react"
import { Ban, Trash2, Save, CheckCircle2, FileSpreadsheet, Plus, Key, BarChart3, FlaskConical, Eye, EyeOff } from "lucide-react"
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

const KEY_INFO: Record<string, { label: string; description: string; url: string }> = {
  brave: { label: "Brave Search", description: "Web search for company discovery. Falls back to DuckDuckGo without a key.", url: "https://brave.com/search/api/" },
  groq: { label: "Groq (LLM)", description: "AI-powered keyword generation, intent judging and relevance matching.", url: "https://console.groq.com/keys" },
  gemini: { label: "Google Gemini", description: "Alternative LLM provider. Used as fallback when Groq is unavailable.", url: "https://aistudio.google.com/apikey" },
  hunter: { label: "Hunter.io", description: "Email verification for decision-maker contacts. Falls back to MX-only check.", url: "https://hunter.io/api-keys" },
  places: { label: "Google Places", description: "Rating, review count and opening hours enrichment. 1K free calls/month.", url: "https://console.cloud.google.com/apis/credentials" },
}

function ApiKeys() {
  const [keys, setKeys] = React.useState<{ key_name: string; created_at: string }[]>([])
  const [encryptionAvailable, setEncryptionAvailable] = React.useState(false)
  const [inputs, setInputs] = React.useState<Record<string, string>>({})
  const [visible, setVisible] = React.useState<Record<string, boolean>>({})
  const [testing, setTesting] = React.useState<string | null>(null)
  const [testResult, setTestResult] = React.useState<Record<string, { ok: boolean; message: string }>>({})
  const [saving, setSaving] = React.useState<string | null>(null)
  const [pref, setPref] = React.useState("")
  const [comment, setComment] = React.useState("")

  const configured = React.useMemo(() => new Set(keys.map((k) => k.key_name)), [keys])

  const load = React.useCallback(() => {
    api.listApiKeys().then((r) => { setKeys(r.keys); setEncryptionAvailable(r.encryption_available) }).catch(() => {})
    api.getPreferences().then((r) => {
      setPref(r.preferences["monetization_preference"] ?? "")
      setComment(r.preferences["monetization_comment"] ?? "")
    }).catch(() => {})
  }, [])
  React.useEffect(() => { load() }, [load])

  const saveKey = async (name: string) => {
    const val = inputs[name]?.trim()
    if (!val) return
    setSaving(name)
    try {
      await api.saveApiKey(name, val)
      setInputs((p) => ({ ...p, [name]: "" }))
      load()
    } catch { /* toast? */ } finally { setSaving(null) }
  }

  const deleteKey = async (name: string) => {
    if (!confirm(`Remove your ${KEY_INFO[name]?.label ?? name} API key?`)) return
    try { await api.deleteApiKey(name); load() } catch { /* */ }
  }

  const testKey = async (name: string) => {
    setTesting(name)
    setTestResult((p) => ({ ...p, [name]: { ok: false, message: "Testing..." } }))
    try {
      const r = await api.testApiKey(name)
      setTestResult((p) => ({ ...p, [name]: r }))
    } catch (e) {
      setTestResult((p) => ({ ...p, [name]: { ok: false, message: (e as Error).message } }))
    } finally { setTesting(null) }
  }

  const savePref = async (key: string, value: string) => {
    try { await api.setPreference(key, value) } catch { /* */ }
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>
            Add your own API keys to unlock premium features. All keys are encrypted at rest.
            Without keys, the engine uses free fallbacks (DuckDuckGo, MX-only verification, no LLM refinement).
          </CardDescription>
          {!encryptionAvailable && (
            <p className="text-sm text-destructive">Encryption not configured on the server (GTM_ENCRYPTION_KEY). API key storage is disabled.</p>
          )}
        </CardHeader>
        <CardContent className="grid gap-4">
          {Object.entries(KEY_INFO).map(([name, info]) => (
            <div key={name} className="rounded-lg border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium text-sm">{info.label}</span>
                  {configured.has(name)
                    ? <Badge className="text-xs">configured</Badge>
                    : <Badge variant="outline" className="text-xs">not configured</Badge>}
                </div>
                <a href={info.url} target="_blank" rel="noopener noreferrer" className="text-xs text-muted-foreground underline">
                  Get a key
                </a>
              </div>
              <p className="text-xs text-muted-foreground mb-3">{info.description}</p>
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative flex-1 min-w-[200px] max-w-sm">
                  <Input
                    type={visible[name] ? "text" : "password"}
                    placeholder={configured.has(name) ? "••••••••" : "Paste your key"}
                    value={inputs[name] ?? ""}
                    onChange={(e) => setInputs((p) => ({ ...p, [name]: e.target.value }))}
                    disabled={!encryptionAvailable}
                    className="pr-8 font-mono text-xs"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                    onClick={() => setVisible((p) => ({ ...p, [name]: !p[name] }))}
                  >
                    {visible[name] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
                <Button size="sm" onClick={() => saveKey(name)} disabled={!encryptionAvailable || !inputs[name]?.trim() || saving === name}>
                  <Save className="h-3.5 w-3.5 mr-1" /> Save
                </Button>
                {configured.has(name) && (
                  <>
                    <Button size="sm" variant="outline" onClick={() => testKey(name)} disabled={testing === name}>
                      <FlaskConical className="h-3.5 w-3.5 mr-1" /> Test
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => deleteKey(name)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </>
                )}
              </div>
              {testResult[name] && (
                <p className={cn("text-xs mt-2", testResult[name].ok ? "text-green-600 dark:text-green-400" : "text-destructive")}>
                  {testResult[name].message}
                </p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>How would you like to use Qualifyr?</CardTitle>
          <CardDescription>Help us understand what works best for you. This is anonymous feedback — it shapes what we build next.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            {[
              { value: "own_keys", label: "I'll bring my own API keys (free tier)" },
              { value: "managed_paid", label: "I'd pay for a managed version (no keys needed)" },
              { value: "undecided", label: "Not sure yet" },
            ].map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio" name="monetization" value={opt.value}
                  checked={pref === opt.value}
                  onChange={() => { setPref(opt.value); savePref("monetization_preference", opt.value) }}
                  className="accent-primary"
                />
                <span className="text-sm">{opt.label}</span>
              </label>
            ))}
          </div>
          <Textarea
            placeholder="What would make the paid version worth it for you? (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onBlur={() => { if (comment.trim()) savePref("monetization_comment", comment.trim()) }}
            rows={3}
            className="text-sm"
          />
        </CardContent>
      </Card>
    </div>
  )
}

function UsageDashboard() {
  const [usage, setUsage] = React.useState<Record<string, { count: number; limit: number }>>({})
  React.useEffect(() => { api.getUsage().then((r) => setUsage(r.usage)).catch(() => {}) }, [])

  const resources = [
    { key: "brave", label: "Brave Search", unit: "searches" },
    { key: "groq", label: "Groq LLM", unit: "calls" },
    { key: "hunter", label: "Hunter.io", unit: "verifications" },
    { key: "places", label: "Google Places", unit: "lookups" },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Daily usage</CardTitle>
        <CardDescription>
          Usage resets at midnight UTC each day. Limits keep the free tier sustainable for everyone.
          When a limit is reached, the engine falls back to free alternatives automatically.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {resources.map((r) => {
          const u = usage[r.key] ?? { count: 0, limit: 50 }
          const pct = Math.min(100, Math.round((u.count / u.limit) * 100))
          return (
            <div key={r.key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">{r.label}</span>
                <span className="text-xs text-muted-foreground">{u.count} / {u.limit} {r.unit}</span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", pct >= 90 ? "bg-destructive" : pct >= 70 ? "bg-yellow-500" : "bg-primary")}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

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
      setStatus({ ok: true, message: `Saved ${r.file ?? r.campaign_id ?? v.campaign_id}` })
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
            <CardDescription>Create or edit a campaign here — a new one is saved to your account. Validation runs the same schema the engine uses.</CardDescription>
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
  const [tab, setTab] = React.useState("api-keys")
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">API keys, usage limits, campaigns, mailboxes and exports.</p>
      </div>
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <TabsList>
          <TabsTrigger value="api-keys"><Key className="h-3.5 w-3.5 mr-1" />API Keys</TabsTrigger>
          <TabsTrigger value="usage"><BarChart3 className="h-3.5 w-3.5 mr-1" />Usage</TabsTrigger>
          <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          <TabsTrigger value="mailboxes">Mailboxes</TabsTrigger>
          <TabsTrigger value="suppressions">Suppressions</TabsTrigger>
          <TabsTrigger value="sheets">Google Sheets</TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === "api-keys" && <ApiKeys />}
      {tab === "usage" && <UsageDashboard />}
      {tab === "campaigns" && <CampaignEditor />}
      {tab === "mailboxes" && <Mailboxes campaignId={campaignId} />}
      {tab === "suppressions" && <Suppressions />}
      {tab === "sheets" && <Sheets campaignId={campaignId} />}
    </div>
  )
}
