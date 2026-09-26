// Thin client for the FastAPI backend. Base URL comes from NEXT_PUBLIC_API_URL.

import { createClient } from "@/lib/supabase/client"
import { supabaseConfigured } from "@/lib/supabase/config"

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
  news_mentions: { title: string; url: string; date: string; source: string }[]
  intent_signals: { kind: string; source: string; source_url: string | null; text: string; organization: string | null; date: string | null; deadline: string | null; matched_terms: string[]; extracted: Record<string, string> | null }[]
  review_verdict: string | null
  reply_label: string | null
  reply_excerpt: string | null
  referred_contact: { name: string | null; email: string; status: string } | null
  domain_age_years: number | null
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

export interface CampaignCreate {
  name: string
  offer: string
  countries: string[]
  provinces: string[]
  cities: string[]
  target_industries: string[]
  buyer_keywords: string[]
  osm_categories: string[]
  overture_categories: string[]
  min_score: number
  max_companies: number
}

export interface Campaign {
  campaign_id: string
  name: string
  offer: string
  file: string | null
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
  reviewed: number
  correct: number
  accuracy: number | null
  verdicts: Record<string, number>
  with_intent: number
}

export interface QueueItem { lead: Lead; step: Step; draft: Draft }
export interface Queue {
  items: QueueItem[]
  counts: Record<SequenceStatus, number>
  smtp_configured: boolean
  daily_limit: number
  sent_today: number
  mailboxes: MailboxState[]
}

export interface Suppression { value: string; kind: string; reason: string | null; created_at: string }

export interface MailboxState {
  address: string
  auth_mode: string
  enabled: boolean
  days_active: number | null
  cap: number
  sent_today: number
  bounced_today: number
  remaining: number
  paused_reason: string | null
}

export interface SendReport {
  sent: number
  skipped: number
  failed: number
  stopped_reason: string | null
  details: string[]
  mode: string
  sync: Record<string, number | string> | null
  mailboxes?: Record<string, MailboxState>
}

/** The current Supabase access token, or null when signed out.
 *
 * Read per request rather than captured once: the SDK rotates the token in the background,
 * and a stale copy would start 401ing an hour into a session. getSession() reads local
 * storage and refreshes only when needed, so this is not a network call in the common case.
 */
async function accessToken(): Promise<string | null> {
  if (typeof window === "undefined" || !supabaseConfigured) return null
  try {
    const { data } = await createClient().auth.getSession()
    return data.session?.access_token ?? null
  } catch {
    return null
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  })
  if (!res.ok) {
    // A 401 means the session lapsed while the tab was open. Send them to sign in rather
    // than surfacing "missing bearer token" inside a table cell, and return them after.
    if (res.status === 401 && typeof window !== "undefined") {
      window.location.assign(`/sign-in?next=${encodeURIComponent(window.location.pathname)}`)
    }
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail))
  }
  // 204 No Content (e.g. DELETE) has an empty body; res.json() would throw on it.
  if (res.status === 204 || res.headers.get("content-length") === "0") return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; version: string; smtp_configured: boolean; require_approval: boolean; auth_mode: string; warmup: { enabled: boolean; start: number; step: number; max: number } }>("/health"),
  campaigns: () => request<Campaign[]>("/campaigns"),
  createCampaign: (body: CampaignCreate) =>
    request<{ campaign_id: string; name: string }>("/campaigns", { method: "POST", body: JSON.stringify(body) }),
  deleteCampaign: (id: string) =>
    request<void>(`/campaigns/${id}`, { method: "DELETE" }),
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
  suppressions: () => request<Suppression[]>("/suppressions"),
  addSuppression: (value: string, reason?: string) =>
    request<{ ok: boolean }>("/suppressions", { method: "POST", body: JSON.stringify({ value, reason }) }),
  removeSuppression: (value: string) => request<{ ok: boolean }>(`/suppressions/${encodeURIComponent(value)}`, { method: "DELETE" }),
  mailboxes: (campaignId?: string) => request<MailboxState[]>(`/mailboxes${campaignId ? `?campaign_id=${campaignId}` : ""}`),
  campaignYaml: (id: string) => request<{ campaign_id: string; file: string; yaml: string }>(`/campaigns/${id}/yaml`),
  validateCampaign: (yaml: string) =>
    request<{ ok: boolean; error?: string; campaign_id: string; name: string; sources: string[] }>("/campaigns/validate", { method: "POST", body: JSON.stringify({ yaml }) }),
  saveCampaignYaml: (id: string, yaml: string) =>
    request<{ ok: boolean; file: string }>(`/campaigns/${id}/yaml`, { method: "PUT", body: JSON.stringify({ yaml }) }),
  sheetsStatus: () => request<{ configured: boolean; spreadsheet_id: string | null }>("/sheets/status"),
  exportSheets: (id: string) => request<{ rows: number; tab: string; url: string }>(`/campaigns/${id}/export/sheets`, { method: "POST" }),
  review: (leadId: string, verdict: string) =>
    request<{ ok: boolean; review_verdict: string | null }>(`/leads/${leadId}/review`, { method: "POST", body: JSON.stringify({ verdict }) }),
  referral: (leadId: string, accept: boolean) =>
    request<{ ok: boolean }>(`/leads/${leadId}/referral`, { method: "POST", body: JSON.stringify({ accept }) }),
  sequence: (id: string) => request<Lead[]>(`/campaigns/${id}/outreach/sequence`),
}

export const STEP_LABEL: Record<Step, string> = {
  email_1: "Email 1", followup_1: "Follow-up 1", followup_2: "Follow-up 2",
}
