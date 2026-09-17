"use client"

import * as React from "react"
import { Play, Download } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { api, type Campaign, type Progress as RunProgress } from "@/lib/api"
import { useCampaign } from "@/components/campaign-context"

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
  const onFinished = React.useCallback(() => { refresh() }, [refresh])

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-bold">Campaigns</h1>
        <p className="text-muted-foreground">One YAML per campaign in <code>config/campaigns/</code>. Run discovery here; results land in Leads.</p>
      </div>
      {error && <p className="text-sm text-destructive">API error: {error}</p>}
      {loading && <p className="text-muted-foreground">Loading…</p>}
      {campaigns.map((c) => (
        <Card key={c.campaign_id}>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle>{c.name}</CardTitle>
                <CardDescription>{c.offer}</CardDescription>
              </div>
              <div className="flex flex-wrap gap-1">
                {c.cities.map((city) => <Badge key={city} variant="outline">{city}</Badge>)}
                <Badge variant="secondary">min score {c.min_score}</Badge>
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
