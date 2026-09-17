"use client"

import * as React from "react"
import { api, type Campaign } from "@/lib/api"

interface Ctx {
  campaigns: Campaign[]
  campaignId: string | null
  setCampaignId: (id: string) => void
  refresh: () => Promise<void>
  loading: boolean
  error: string | null
}

const CampaignContext = React.createContext<Ctx | null>(null)

export function CampaignProvider({ children }: { children: React.ReactNode }) {
  const [campaigns, setCampaigns] = React.useState<Campaign[]>([])
  const [campaignId, setCampaignIdState] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    try {
      const list = await api.campaigns()
      setCampaigns(list)
      setError(null)
      setCampaignIdState((cur) => {
        if (cur && list.some((c) => c.campaign_id === cur)) return cur
        let saved: string | null = null
        try { saved = localStorage.getItem("qualifyr.campaign") } catch { /* ignore */ }
        const pick = list.find((c) => c.campaign_id === saved) ?? list[0]
        return pick?.campaign_id ?? null
      })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { refresh() }, [refresh])

  const setCampaignId = (id: string) => {
    setCampaignIdState(id)
    try { localStorage.setItem("qualifyr.campaign", id) } catch { /* ignore */ }
  }

  return (
    <CampaignContext.Provider value={{ campaigns, campaignId, setCampaignId, refresh, loading, error }}>
      {children}
    </CampaignContext.Provider>
  )
}

export function useCampaign(): Ctx {
  const ctx = React.useContext(CampaignContext)
  if (!ctx) throw new Error("useCampaign outside CampaignProvider")
  return ctx
}
