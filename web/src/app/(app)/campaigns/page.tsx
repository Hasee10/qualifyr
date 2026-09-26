"use client"

import * as React from "react"
import { Play, Download, Plus, Trash2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { api, type Campaign, type Progress as RunProgress } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"

const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean)

function NewCampaign({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [name, setName] = React.useState("")
  const [offer, setOffer] = React.useState("")
  const [countries, setCountries] = React.useState("Pakistan")
  const [cities, setCities] = React.useState("")
  const [industries, setIndustries] = React.useState("")
  const [buyerKeywords, setBuyerKeywords] = React.useState("")
  const [osm, setOsm] = React.useState("")
  const [overture, setOverture] = React.useState("")
  const [minScore, setMinScore] = React.useState("70")
  const [maxCompanies, setMaxCompanies] = React.useState("60")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const submit = async () => {
    setError(null)
    if (!name.trim() || !offer.trim()) { setError("Name and offer are required."); return }
    setBusy(true)
    try {
      await api.createCampaign({
        name: name.trim(), offer: offer.trim(),
        countries: csv(countries), cities: csv(cities),
        target_industries: csv(industries), buyer_keywords: csv(buyerKeywords),
        osm_categories: csv(osm), overture_categories: csv(overture),
        min_score: Number(minScore) || 70, max_companies: Number(maxCompanies) || 60,
      })
      onCreated(); onClose()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader><SheetTitle>New campaign</SheetTitle></SheetHeader>
        <div className="flex flex-col gap-4 p-4 pt-0">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Retail & apparel, Lahore" />
          </div>
          <div className="grid gap-1.5">
            <Label>What you offer</Label>
            <Textarea rows={2} value={offer} onChange={(e) => setOffer(e.target.value)} placeholder="Order-management and inventory software for growing retailers" />
            <p className="text-xs text-muted-foreground">Used for context and personalization. Keyword generation will build on this.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Countries</Label><Input value={countries} onChange={(e) => setCountries(e.target.value)} placeholder="Pakistan" /></div>
            <div className="grid gap-1.5"><Label>Cities</Label><Input value={cities} onChange={(e) => setCities(e.target.value)} placeholder="Lahore, Karachi" /></div>
          </div>
          <div className="grid gap-1.5">
            <Label>Target industries</Label>
            <Input value={industries} onChange={(e) => setIndustries(e.target.value)} placeholder="retail, clothing, fashion" />
          </div>
          <div className="grid gap-1.5">
            <Label>Buyer keywords</Label>
            <Input value={buyerKeywords} onChange={(e) => setBuyerKeywords(e.target.value)} placeholder="retailer, store, brand, outlet" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>OSM categories</Label><Input value={osm} onChange={(e) => setOsm(e.target.value)} placeholder="shop=clothes" /></div>
            <div className="grid gap-1.5"><Label>Overture categories</Label><Input value={overture} onChange={(e) => setOverture(e.target.value)} placeholder="clothing_store" /></div>
          </div>
          <p className="text-xs text-muted-foreground">Comma-separated. At least one discovery source (OSM or Overture category) is recommended so the crawl has somewhere to look.</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Min score</Label><Input value={minScore} onChange={(e) => setMinScore(e.target.value)} /></div>
            <div className="grid gap-1.5"><Label>Companies per run (API cap)</Label><Input value={maxCompanies} onChange={(e) => setMaxCompanies(e.target.value)} /></div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button onClick={submit} disabled={busy}>{busy ? "Creating…" : "Create campaign"}</Button>
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
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Companies to process</span>
        <Input className="w-24" value={max} onChange={(e) => setMax(e.target.value)} disabled={!!running} />
        <Button onClick={start} disabled={!!running}>
          <Play data-icon="inline-start" /> {running ? "Running…" : "Run discovery"}
        </Button>
        <a href={api.exportUrl(campaign.campaign_id, campaign.min_score)}>
          <Button variant="outline"><Download data-icon="inline-start" /> Qualified CSV</Button>
        </a>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {progress && progress.stage !== "idle" && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-sm">
            <Badge variant={progress.stage === "failed" ? "destructive" : progress.stage === "completed" ? "default" : "secondary"}>
              {progress.stage}
            </Badge>
            <span className="text-muted-foreground">
              {progress.stage === "discover" ? `${progress.done} companies found` : progress.total ? `${progress.done}/${progress.total}` : ""} {progress.message}
            </span>
          </div>
          {progress.stage === "process" && <Progress value={pct} className="h-2" />}
          {stats && (
            <p className="text-xs text-muted-foreground">
              discovered {stats.discovered} → {stats.after_dedupe} unique · BUYER {stats.buyer} · VENDOR {stats.vendor} · UNKNOWN {stats.unknown} · qualified {stats.qualified} · outreach-ready {stats.outreach_ready} · unreachable {stats.unreachable}
            </p>
          )}
        </div>
      )}
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
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Campaigns</h1>
          <p className="text-muted-foreground">Create a search, run discovery, and results land in Leads. Each run keeps its history.</p>
        </div>
        <Button onClick={() => setCreating(true)}><Plus data-icon="inline-start" /> New campaign</Button>
      </div>
      <NewCampaign open={creating} onClose={() => setCreating(false)} onCreated={onCreated} />
      {error && <p className="text-sm text-destructive">API error: {error}</p>}
      {loading && <p className="text-muted-foreground">Loading…</p>}
      {!loading && campaigns.length === 0 && (
        <Card><CardContent className="py-10 text-center text-muted-foreground">No campaigns yet. Create one to start a search.</CardContent></Card>
      )}
      {campaigns.map((c) => (
        <Card key={c.campaign_id}>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle>{c.name}</CardTitle>
                <CardDescription>{c.offer}</CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {c.cities.map((city) => <Badge key={city} variant="outline">{city}</Badge>)}
                <Badge variant="secondary">min score {c.min_score}</Badge>
                {!c.file && (
                  <Button variant="ghost" size="sm" onClick={() => remove(c)} aria-label="Delete campaign" className="text-muted-foreground hover:text-destructive">
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2 text-sm sm:grid-cols-4">
              <div><span className="text-muted-foreground">Companies</span><div className="text-xl font-semibold">{c.leads}</div></div>
              <div><span className="text-muted-foreground">Buyers</span><div className="text-xl font-semibold">{c.buyers}</div></div>
              <div><span className="text-muted-foreground">Qualified</span><div className="text-xl font-semibold">{c.qualified}</div></div>
              <div><span className="text-muted-foreground">Outreach-ready</span><div className="text-xl font-semibold">{c.outreach_ready}</div></div>
            </div>
            {c.last_run && (
              <p className="text-xs text-muted-foreground">
                Last run {c.last_run.run_id} · {c.last_run.status} · {new Date(c.last_run.started_at).toLocaleString()}
              </p>
            )}
            <RunPanel campaign={c} onFinished={onFinished} />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
