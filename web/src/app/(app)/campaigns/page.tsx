"use client"

import * as React from "react"
import { Play, Download, Plus, Trash2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { api, type Campaign, type Progress as RunProgress } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"

function NewCampaign({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [text, setText] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<{ config: Record<string, unknown>; explanation: string } | null>(null)

  const submit = async () => {
    setError(null)
    if (!text.trim()) { setError("Describe what you're looking for."); return }
    setBusy(true)
    try {
      const res = await api.createCampaignNL(text.trim())
      setResult({ config: res.config, explanation: res.explanation })
      onCreated()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const close = () => { setText(""); setError(null); setResult(null); onClose() }

  const cfg = result?.config
  const chips: { label: string; value: string }[] = []
  if (cfg) {
    if (cfg.name) chips.push({ label: "Name", value: String(cfg.name) })
    const cities = cfg.geography && typeof cfg.geography === "object" && "cities" in cfg.geography ? (cfg.geography as Record<string, unknown>).cities : null
    if (Array.isArray(cities) && cities.length) chips.push({ label: "Cities", value: cities.join(", ") })
    if (Array.isArray(cfg.target_industries) && cfg.target_industries.length) chips.push({ label: "Industries", value: cfg.target_industries.join(", ") })
    if (cfg.offer) chips.push({ label: "Offer", value: String(cfg.offer) })
  }

  return (
    <Sheet open={open} onOpenChange={(o) => !o && close()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader><SheetTitle>New campaign</SheetTitle></SheetHeader>
        <div className="flex flex-col gap-4 p-4 pt-0">
          {!result ? (
            <>
              <p className="text-sm text-muted-foreground">Describe what you&apos;re looking for in plain English. The engine figures out the cities, industries, and search categories automatically.</p>
              <Textarea
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Find grocery stores in Islamabad that need inventory management software"
                autoFocus
              />
              <div className="flex flex-wrap gap-1.5">
                {["find bakeries in Lahore", "grocery stores in Islamabad needing POS systems", "clothing retailers in Karachi without an online store"].map((ex) => (
                  <button key={ex} type="button" onClick={() => setText(ex)} className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground hover:bg-muted transition-colors">
                    {ex}
                  </button>
                ))}
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={close} disabled={busy}>Cancel</Button>
                <Button onClick={submit} disabled={busy}>{busy ? "Creating…" : "Create campaign"}</Button>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-lg border bg-muted/30 p-3">
                <p className="text-sm font-medium mb-2">Campaign created</p>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {chips.map((c) => (
                    <Badge key={c.label} variant="outline"><span className="font-medium mr-1">{c.label}:</span> {c.value}</Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">{result.explanation}</p>
              </div>
              <div className="flex justify-end">
                <Button onClick={close}>Done</Button>
              </div>
            </>
          )}
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
              {stats.intent_dropped_irrelevant ? ` · ${stats.intent_dropped_irrelevant} off-offer signal(s) dropped` : ""}
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
            {c.discovery_sectors && c.discovery_sectors.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Searching sectors:</span>
                {c.discovery_sectors.map((s) => <Badge key={s} variant="outline" className="font-normal">{s.replace(/_/g, " ")}</Badge>)}
              </div>
            )}
            {c.relevance_keywords && c.relevance_keywords.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Relevance keywords:</span>
                {c.relevance_keywords.slice(0, 12).map((k) => <Badge key={k} variant="secondary" className="font-normal">{k}</Badge>)}
                {c.relevance_keywords.length > 12 && <span className="text-xs text-muted-foreground">+{c.relevance_keywords.length - 12}</span>}
              </div>
            )}
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
