import { Badge } from "@/components/ui/badge"
import type { CompanyType, SequenceStatus } from "@/lib/api"

export function TypeBadge({ type }: { type: CompanyType }) {
  const variant = type === "BUYER" ? "default" : type === "VENDOR" ? "destructive" : "outline"
  return <Badge variant={variant}>{type}</Badge>
}

export function ScoreBadge({ score }: { score: number }) {
  const variant = score >= 80 ? "default" : score >= 70 ? "secondary" : "outline"
  return <Badge variant={variant} className="tabular-nums">{score}</Badge>
}

const STATUS_LABEL: Record<SequenceStatus, string> = {
  not_queued: "Not queued", queued: "Queued", email_1_sent: "Email 1 sent",
  followup_1_sent: "Follow-up 1 sent", followup_2_sent: "Sequence done", completed: "Done",
  replied: "Replied", bounced: "Bounced", unsubscribed: "Unsubscribed", suppressed: "Suppressed",
}

export function StatusBadge({ status }: { status: SequenceStatus }) {
  const variant =
    status === "replied" ? "default"
    : status === "bounced" || status === "unsubscribed" || status === "suppressed" ? "destructive"
    : status === "not_queued" ? "outline" : "secondary"
  return <Badge variant={variant}>{STATUS_LABEL[status] ?? status}</Badge>
}

export function EmailStatusBadge({ status }: { status: string }) {
  const variant = status === "deliverable" || status === "mx_valid" ? "default"
    : status === "generic" ? "secondary"
    : status === "invalid" || status === "risky" ? "destructive" : "outline"
  return <Badge variant={variant}>{status.replace("_", " ")}</Badge>
}
