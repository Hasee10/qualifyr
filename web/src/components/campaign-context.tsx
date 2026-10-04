"use client"

import * as React from "react"
import { api, PENDING_MONETIZATION_KEY, type Campaign } from "@/lib/api"

interface Ctx {
  campaigns: Campaign[]
  campaignId: string | null
  setCampaignId: (id: string) => void
  refresh: (force?: boolean) => Promise<void>
  loading: boolean
  error: string | null
}

const CampaignContext = React.createContext<Ctx | null>(null)

export function CampaignProvider({ children }: { children: React.ReactNode }) {
  const [campaigns, setCampaigns] = React.useState<Campaign[]>([])
  const [campaignId, setCampaignIdState] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const lastFetch = React.useRef(0)

  const refresh = React.useCallback(async (force = false) => {
    const now = Date.now()
    if (!force && now - lastFetch.current < 5000) return
    lastFetch.current = now
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

  React.useEffect(() => { refresh(true) }, [refresh])

  // Flush the sign-up monetization vote once there is an authenticated session (it may have
  // been stashed before e-mail confirmation, when no token existed yet).
  React.useEffect(() => {
    let pending: string | null = null
    try { pending = localStorage.getItem(PENDING_MONETIZATION_KEY) } catch { /* ignore */ }
    if (!pending) return
    api.setPreference("monetization_preference", pending)
      .then(() => { try { localStorage.removeItem(PENDING_MONETIZATION_KEY) } catch { /* ignore */ } })
      .catch(() => { /* retried on next load */ })
  }, [])

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
