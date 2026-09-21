// Thin client for the FastAPI backend. Base URL comes from NEXT_PUBLIC_API_URL.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type CompanyType = "BUYER" | "VENDOR" | "UNKNOWN"
export type SequenceStatus =
  | "not_queued" | "queued" | "email_1_sent" | "followup_1_sent" | "followup_2_sent"
  | "completed" | "replied" | "bounced" | "unsubscribed" | "suppressed"
export type Step = "email_1" | "followup_1" | "followup_2"

export interface Lead {
  lead_id: string
  campaign_id: string
  company_name: string
  domain: string | null
  website: string | null
  country: string | null
  city: string | null
  industry: string | null
  company_description: string | null
  company_type: CompanyType
  buyer_fit_reason: string
  total_score: number
  score_reason: string
  contact_name: string | null
  contact_role: string | null
  contact_email: string | null
  email_status: string
  phone: string | null
  linkedin_or_public_profile_url: string | null
  personalization_hook: string | null
  buying_signal: string | null
  pain_signal: string | null
  source: string
  source_url: string | null
  outreach_ready: boolean
  sequence_status: SequenceStatus
  priority: "high_priority" | "qualified" | "review" | "reject"
  technologies: string[]
  phone_type: string | null
  candidate_email: string | null
  provenance: Record<string, string>
  email_1_sent_at: string | null
  followup_1_at: string | null
  followup_2_at: string | null
  next_contact_at: string | null
  reply_status: string | null
  events?: OutreachEvent[]
  drafts?: Draft[]
}

export interface Draft {
  lead_id: string
  step: Step
  subject: string
  body: string
  status: "pending" | "approved" | "rejected" | "sent"
  edited: number
  created_at: string
  approved_at: string | null
}

export interface OutreachEvent {
  event_id: number
  lead_id: string
  event_type: string
  step: string | null
  detail: string | null
  created_at: string
  company_name?: string
  contact_email?: string
}

export interface Campaign {
  campaign_id: string
  name: string
  offer: string
  file: string
  cities: string[]
  countries: string[]
  min_score: number
  max_companies: number
  leads: number
  buyers: number
  qualified: number
  outreach_ready: number
  last_run: { run_id: string; status: string; started_at: string; finished_at: string | null; stats_json: string | null } | null
  live: Progress | null
}

export interface Progress {
  run_id: string | null
  stage: string
  done: number
  total: number
  message: string
  stats: Record<string, number> | null
}

export interface Stats {
  campaign_id: string
  leads: number
  by_type: Record<CompanyType, number>
  by_status: Record<SequenceStatus, number>
  by_priority: Record<string, number>
  score_bands: Record<string, number>
  qualified: number
  outreach_ready: number
  emails_sent: number
  replied: number
  bounced: number
}

export interface QueueItem { lead: Lead; step: Step; draft: Draft }
export interface Queue {
  items: QueueItem[]
  counts: Record<SequenceStatus, number>
  smtp_configured: boolean
  daily_limit: number
  sent_today: number
}

export interface SendReport {
  sent: number
  skipped: number
  failed: number
  stopped_reason: string | null
  details: string[]
  mode: string
  sync: Record<string, number | string> | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; version: string; smtp_configured: boolean; require_approval: boolean; auth_mode: string; warmup: { enabled: boolean; start: number; step: number; max: number } }>("/health"),
  campaigns: () => request<Campaign[]>("/campaigns"),
  runCampaign: (id: string, max_companies?: number) =>
    request<Progress>(`/campaigns/${id}/run`, { method: "POST", body: JSON.stringify({ max_companies }) }),
  progress: (id: string) => request<Progress>(`/campaigns/${id}/progress`),
  stats: (id: string) => request<Stats>(`/campaigns/${id}/stats`),
  leads: (id: string, q: { min_score?: number; company_type?: string; outreach_ready?: boolean } = {}) => {
    const p = new URLSearchParams()
    if (q.min_score) p.set("min_score", String(q.min_score))
    if (q.company_type) p.set("company_type", q.company_type)
    if (q.outreach_ready !== undefined) p.set("outreach_ready", String(q.outreach_ready))
    return request<Lead[]>(`/campaigns/${id}/leads?${p}`)
  },
  lead: (leadId: string) => request<Lead>(`/leads/${leadId}`),
  suppress: (leadId: string, reason?: string) =>
    request<{ ok: boolean }>(`/leads/${leadId}/suppress`, { method: "POST", body: JSON.stringify({ reason }) }),
  exportUrl: (id: string, min_score = 70, buyers_only = true) =>
    `${API_URL}/campaigns/${id}/export?min_score=${min_score}&buyers_only=${buyers_only}`,
  queue: (id: string) => request<Queue>(`/campaigns/${id}/outreach/queue`),
  draft: (leadId: string, step: Step) => request<Draft>(`/leads/${leadId}/drafts/${step}`),
  saveDraft: (leadId: string, step: Step, subject: string, body: string) =>
    request<Draft>(`/leads/${leadId}/drafts/${step}`, { method: "PUT", body: JSON.stringify({ subject, body }) }),
  approve: (leadId: string, step: Step) => request<Draft>(`/leads/${leadId}/drafts/${step}/approve`, { method: "POST" }),
  reject: (leadId: string, step: Step) => request<Draft>(`/leads/${leadId}/drafts/${step}/reject`, { method: "POST" }),
  resetDraft: (leadId: string, step: Step) => request<Draft>(`/leads/${leadId}/drafts/${step}/reset`, { method: "POST" }),
  send: (id: string, body: { limit?: number; dry_run?: boolean; ignore_window?: boolean }) =>
    request<SendReport>(`/campaigns/${id}/outreach/send`, { method: "POST", body: JSON.stringify(body) }),
  sync: (id: string) => request<SendReport["sync"] & { details: string[] }>(`/campaigns/${id}/outreach/sync`, { method: "POST" }),
  activity: (id: string) => request<OutreachEvent[]>(`/campaigns/${id}/outreach/activity`),
  sequence: (id: string) => request<Lead[]>(`/campaigns/${id}/outreach/sequence`),
}

export const STEP_LABEL: Record<Step, string> = {
  email_1: "Email 1", followup_1: "Follow-up 1", followup_2: "Follow-up 2",
}
