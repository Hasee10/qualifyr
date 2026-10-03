"use client"

import * as React from "react"
import { Play, Download, Plus, Trash2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { api, type Campaign, type Progress as RunProgress } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"

function NewCampaign({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  // NL mode state
  const [text, setText] = React.useState("")
  // Manual mode state
  const [name, setName] = React.useState("")
  const [offer, setOffer] = React.useState("")
  const [industries, setIndustries] = React.useState("")
  const [cities, setCities] = React.useState("")
  const [keywords, setKeywords] = React.useState("")
  const [categories, setCategories] = React.useState("")
  const [searchQueries, setSearchQueries] = React.useState("")
  // Shared state
  const [maxCo, setMaxCo] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<{ campaignId: string; config: Record<string, unknown>; explanation: Record<string, unknown> | string } | null>(null)
  // Key availability
  const [hasGroq, setHasGroq] = React.useState<boolean | null>(null)
  const [hasBrave, setHasBrave] = React.useState<boolean | null>(null)

  React.useEffect(() => {
    if (!open) return
    api.listApiKeys().then((r) => {
      const names = new Set(r.keys.map((k) => k.key_name))
      setHasGroq(names.has("groq"))
      setHasBrave(names.has("brave"))
    }).catch(() => { setHasGroq(false); setHasBrave(false) })
  }, [open])

  const nlMode = hasGroq === true

  const submitNL = async () => {
    setError(null)
    if (!text.trim()) { setError("Describe what you're looking for."); return }
    setBusy(true)
    try {
      const mc = maxCo.trim() ? parseInt(maxCo, 10) : undefined
      const res = await api.createCampaignNL(text.trim(), mc ? { max_companies: mc } : undefined)
      setResult({ campaignId: res.campaign_id, config: res.config, explanation: res.explanation })
      const returned = typeof res.explanation === "object" && res.explanation?.max_companies
      if (returned) setMaxCo(String(returned))
      onCreated()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const submitManual = async () => {
    setError(null)
    if (!name.trim() || !offer.trim()) { setError("Name and offer are required."); return }
    setBusy(true)
    try {
      const body = {
        name: name.trim(),
        offer: offer.trim(),
        countries: ["Pakistan"],
        provinces: [] as string[],
        cities: cities.trim() ? cities.split(",").map((s) => s.trim()).filter(Boolean) : [],
        target_industries: industries.trim() ? industries.split(",").map((s) => s.trim()).filter(Boolean) : [],
        buyer_keywords: keywords.trim() ? keywords.split(",").map((s) => s.trim()).filter(Boolean) : [],
        osm_categories: categories.trim() ? categories.split(",").map((s) => s.trim()).filter(Boolean) : [],
        overture_categories: [] as string[],
        min_score: 70,
        max_companies: maxCo.trim() ? parseInt(maxCo, 10) : 60,
      }
      const res = await api.createCampaign(body)
      setResult({ campaignId: res.campaign_id, config: body as unknown as Record<string, unknown>, explanation: `Campaign "${res.name}" created` })
      onCreated()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const runNow = async () => {
    if (!result) return
    try {
      await api.runCampaign(result.campaignId, Number(maxCo) || undefined)
    } catch { /* run will show in the campaign card */ }
    close()
  }

  const close = () => {
    setText(""); setName(""); setOffer(""); setIndustries(""); setCities("")
    setKeywords(""); setCategories(""); setSearchQueries(""); setMaxCo("")
    setError(null); setResult(null); onClose()
  }

  const exp = result?.explanation
  const rows: { label: string; value: string }[] = []
  if (exp && typeof exp === "object") {
    const e = exp as Record<string, unknown>
    if (e.offer_detected || e.offer) rows.push({ label: "Offer", value: String(e.offer_detected ?? e.offer) })
    if (Array.isArray(e.cities) && e.cities.length) rows.push({ label: "Cities", value: e.cities.join(", ") })
    if (Array.isArray(e.provinces) && e.provinces.length) rows.push({ label: "Provinces", value: e.provinces.join(", ") })
    if (Array.isArray(e.sectors_matched) && e.sectors_matched.length) rows.push({ label: "Sectors", value: e.sectors_matched.join(", ") })
  }

  const loading = hasGroq === null

  return (
    <Sheet open={open} onOpenChange={(o) => !o && close()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader><SheetTitle>New campaign</SheetTitle></SheetHeader>
        <div className="flex flex-col gap-4 p-4 pt-0">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : nlMode ? (
            <>
              <p className="text-sm text-muted-foreground">Describe what you&apos;re looking for in plain English. The engine figures out the cities, industries, and search categories automatically.</p>
              <Textarea
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Find grocery stores in Islamabad that need inventory management software"
                autoFocus
              />
              {!hasBrave && !result && (
                <div className="rounded-lg border border-dashed p-3 grid gap-2">
                  <p className="text-xs font-medium text-muted-foreground">No Brave API key — provide search hints to improve discovery:</p>
                  <Input
                    value={categories}
                    onChange={(e) => setCategories(e.target.value)}
                    placeholder="OSM categories: shop=supermarket, shop=convenience"
                    className="text-xs"
                  />
                  <Input
                    value={searchQueries}
                    onChange={(e) => setSearchQueries(e.target.value)}
                    placeholder="Search queries: grocery stores Islamabad, marts near F-11"
                    className="text-xs"
                  />
                </div>
              )}
              {!result && (
                <div className="flex flex-wrap gap-1.5">
                  {["find bakeries in Lahore", "grocery stores in Islamabad needing POS systems", "clothing retailers in Karachi without an online store"].map((ex) => (
                    <button key={ex} type="button" onClick={() => setText(ex)} className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground hover:bg-muted transition-colors">
                      {ex}
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/30 p-3">
                <p className="text-xs text-blue-700 dark:text-blue-300">Add a <strong>Groq API key</strong> in Settings → API Keys to unlock automatic mode — describe what you want in plain English and the engine handles the rest.</p>
              </div>
              <div className="grid gap-3">
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium">Campaign name *</label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Grocery stores Islamabad" autoFocus />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium">What you sell / offer *</label>
                  <Textarea rows={2} value={offer} onChange={(e) => setOffer(e.target.value)} placeholder="POS and inventory management software for retail stores" />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium">Target industries <span className="text-muted-foreground font-normal">(comma-separated)</span></label>
                  <Input value={industries} onChange={(e) => setIndustries(e.target.value)} placeholder="retail, grocery, supermarket" />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium">Cities <span className="text-muted-foreground font-normal">(comma-separated)</span></label>
                  <Input value={cities} onChange={(e) => setCities(e.target.value)} placeholder="Islamabad, Rawalpindi" />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium">Buyer keywords <span className="text-muted-foreground font-normal">(comma-separated)</span></label>
                  <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="store, mart, shop, retailer" />
                </div>
                {!hasBrave && (
                  <div className="grid gap-1.5">
                    <label className="text-xs font-medium">OSM categories <span className="text-muted-foreground font-normal">(comma-separated, e.g. shop=supermarket)</span></label>
                    <Input value={categories} onChange={(e) => setCategories(e.target.value)} placeholder="shop=supermarket, shop=convenience" />
                  </div>
                )}
              </div>
            </>
          )}
          <div className="flex items-center gap-2">
            <label htmlFor="max-co" className="text-sm text-muted-foreground whitespace-nowrap">Max companies</label>
            <input
              id="max-co"
              type="number"
              min={1}
              max={500}
              value={maxCo}
              onChange={(e) => setMaxCo(e.target.value)}
              placeholder="30"
              className="w-20 rounded-md border bg-transparent px-2 py-1 text-sm"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {result && (
            <div className="rounded-lg border bg-muted/30 p-3">
              <p className="text-sm font-medium mb-3">Campaign created</p>
              {typeof exp === "string" ? (
                <p className="text-sm text-muted-foreground">{exp}</p>
              ) : (
                <div className="grid gap-2">
                  {rows.map((r) => (
                    <div key={r.label} className="flex gap-2 text-sm">
                      <span className="shrink-0 font-medium text-muted-foreground w-28">{r.label}</span>
                      <span className="break-words min-w-0">{r.value}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-3 flex gap-2">
                <Button size="sm" onClick={runNow}><Play data-icon="inline-start" /> Run now</Button>
                <p className="text-xs text-muted-foreground self-center">Starts discovery immediately. Progress shows on the campaign card.</p>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={close} disabled={busy}>Cancel</Button>
            <Button onClick={nlMode ? submitNL : submitManual} disabled={busy || loading}>
              {busy ? "Creating…" : result ? "Recreate campaign" : "Create campaign"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function RunPanel({ campaign, onFinished }: { campaign: Campaign; onFinished: () => void }) {
  const [max, setMax] = React.useState(String(campaign.max_companies))
  const [progress, setProgress] = React.useState<RunProgress | null>(campaign.live)
  const [error, setError] = React.useState<string | null>(null)
  const running = progress && !["idle", "completed", "failed"].includes(progress.stage)

  React.useEffect(() => {
    if (!running) return
    const t = setInterval(async () => {
      try {
        const p = await api.progress(campaign.campaign_id)
        setProgress(p)
        if (p.stage === "completed" || p.stage === "failed") onFinished()
      } catch { /* keep polling */ }
    }, 1500)
    return () => clearInterval(t)
  }, [running, campaign.campaign_id, onFinished])

  const start = async () => {
    setError(null)
    try {
      setProgress(await api.runCampaign(campaign.campaign_id, Number(max) || undefined))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const pct = progress && progress.total ? Math.round((progress.done / progress.total) * 100) : 0
  const stats = progress?.stats

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-20 h-8 text-sm" value={max} onChange={(e) => setMax(e.target.value)} disabled={!!running} />
        <Button size="sm" onClick={start} disabled={!!running}>
          <Play className="size-3.5" /> {running ? "Running…" : "Run"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => api.downloadExport(campaign.campaign_id, { min_score: campaign.min_score })}>
          <Download className="size-3.5" /> CSV
        </Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      {progress && progress.stage !== "idle" && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs">
            <Badge variant={progress.stage === "failed" ? "destructive" : progress.stage === "completed" ? "default" : "secondary"} className="text-[10px] px-1.5 py-0">
              {progress.stage}
            </Badge>
            <span className="text-muted-foreground">
              {progress.stage === "discover" ? `${progress.done} found` : progress.total ? `${progress.done}/${progress.total}` : ""} {progress.message}
            </span>
          </div>
          {progress.stage === "process" && <Progress value={pct} className="h-1.5" />}
          {stats && (
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {stats.discovered} discovered → {stats.after_dedupe} unique · {stats.buyer} buyers · {stats.qualified} qualified · {stats.outreach_ready} outreach-ready
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <div className="text-lg font-semibold leading-none">{value}</div>
      <div className="text-[11px] text-muted-foreground mt-0.5">{label}</div>
    </div>
  )
}

export default function CampaignsPage() {
  const { campaigns, refresh, loading, error } = useCampaign()
  const [creating, setCreating] = React.useState(false)
  const onFinished = React.useCallback(() => { refresh() }, [refresh])

  const onCreated = React.useCallback(async () => { await refresh() }, [refresh])

  const remove = async (c: Campaign) => {
    if (!confirm(`Delete campaign "${c.name}"? Leads already generated are kept.`)) return
    try { await api.deleteCampaign(c.campaign_id); await refresh() } catch (e) { alert((e as Error).message) }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Campaigns</h1>
          <p className="text-sm text-muted-foreground">Create a search, run discovery, and results land in Leads.</p>
        </div>
        <Button onClick={() => setCreating(true)}><Plus data-icon="inline-start" /> New campaign</Button>
      </div>
      <NewCampaign open={creating} onClose={() => setCreating(false)} onCreated={onCreated} />
      {error && <p className="text-sm text-destructive">API error: {error}</p>}
      {loading && <p className="text-muted-foreground">Loading…</p>}
      {!loading && campaigns.length === 0 && (
        <Card><CardContent className="py-10 text-center text-muted-foreground">No campaigns yet. Create one to start a search.</CardContent></Card>
      )}
      {campaigns.map((c) => {
        const offer = typeof c.offer === "string" ? c.offer : JSON.stringify(c.offer)
        const showOffer = offer !== c.name

        return (
          <Card key={c.campaign_id} className="overflow-hidden">
            <CardContent className="p-4 grid gap-3">
              {/* Header row */}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-medium truncate">{c.name}</h3>
                  {showOffer && <p className="text-sm text-muted-foreground truncate">{offer}</p>}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {c.cities.map((city) => <Badge key={city} variant="outline" className="text-[11px] px-1.5 py-0">{city}</Badge>)}
                  {!c.file && (
                    <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-destructive" onClick={() => remove(c)}>
                      <Trash2 className="size-3.5" />
                    </Button>
                  )}
                </div>
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-6">
                <Stat label="Companies" value={c.leads} />
                <Stat label="Buyers" value={c.buyers} />
                <Stat label="Qualified" value={c.qualified} />
                <Stat label="Outreach" value={c.outreach_ready} />
                <div className="ml-auto">
                  <RunPanel campaign={c} onFinished={onFinished} />
                </div>
              </div>

              {/* Last run — compact */}
              {c.last_run && (
                <p className="text-[11px] text-muted-foreground">
                  Last run: {c.last_run.status} · {new Date(c.last_run.started_at).toLocaleDateString()}
                </p>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
