"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, Users, Send, Radar, Menu, Settings } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import { CampaignProvider, useCampaign } from "@/components/campaign-context"
import { ThemeToggle } from "@/components/theme-toggle"
import { SignOutButton } from "@/components/sign-out-button"
import { QualifyrMark } from "@/components/qualifyr-mark"

const nav = [
  // "/" is the public landing page now; the dashboard lives at /dashboard.
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
  { icon: Radar, label: "Campaigns", href: "/campaigns" },
  { icon: Users, label: "Leads", href: "/leads" },
  { icon: Send, label: "Outreach", href: "/outreach" },
  { icon: Settings, label: "Settings", href: "/settings" },
]

function SidebarContent() {
  const pathname = usePathname()
  return (
    <div className="flex h-full flex-col">
      <Link href="/dashboard" className="flex items-center gap-2.5 px-5 py-6">
        <span className="flex size-9 items-center justify-center rounded-xl bg-brand shadow-sm">
          <QualifyrMark className="size-5 text-brand-foreground" />
        </span>
        <span className="text-lg font-semibold tracking-tight">Qualifyr</span>
      </Link>
      <Separator />
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="flex flex-col gap-1">
          {nav.map((item) => {
            const active = pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group inline-flex shrink-0 items-center justify-start gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                <item.icon className={cn("size-4 transition-colors", active ? "text-foreground" : "text-muted-foreground group-hover:text-foreground")} />
                {item.label}
              </Link>
            )
          })}
        </div>
      </nav>
      <Separator />
      <BackendStatus />
    </div>
  )
}

function BackendStatus() {
  const [health, setHealth] = React.useState<"up" | "down" | null>(null)
  React.useEffect(() => {
    api.health().then(() => setHealth("up")).catch(() => setHealth("down"))
  }, [])
  return (
    <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground">
      {health === "down" ? (
        <Badge variant="destructive">API offline</Badge>
      ) : health === "up" ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-green-500" /> API connected
        </span>
      ) : (
        <span>Connecting…</span>
      )}
    </div>
  )
}

function HeaderCampaign() {
  const pathname = usePathname()
  // The Campaigns page lists every campaign as a card, so the header picker is redundant there.
  if (pathname.startsWith("/campaigns")) return null
  return (
    <>
      <span className="text-xs uppercase tracking-wide text-muted-foreground">Campaign</span>
      <CampaignPicker />
    </>
  )
}

function CampaignPicker() {
  const { campaigns, campaignId, setCampaignId } = useCampaign()
  if (campaigns.length <= 1) {
    return <span className="text-sm text-muted-foreground">{campaigns[0]?.name ?? "No campaigns"}</span>
  }
  return (
    <select
      className="h-8 rounded-lg border border-input bg-background px-2 text-sm text-foreground"
      value={campaignId ?? ""}
      onChange={(e) => setCampaignId(e.target.value)}
    >
      {campaigns.map((c) => (
        <option key={c.campaign_id} value={c.campaign_id} className="bg-background text-foreground">{c.name}</option>
      ))}
    </select>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <div className="sticky top-0 flex h-screen flex-col overflow-y-auto">
          <SidebarContent />
        </div>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b bg-card px-6">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger className="lg:hidden">
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <SheetHeader className="sr-only"><SheetTitle>Navigation</SheetTitle></SheetHeader>
              <SidebarContent />
            </SheetContent>
          </Sheet>
          <div className="flex flex-1 items-center gap-4">
            <HeaderCampaign />
          </div>
          <ThemeToggle />
          <SignOutButton />
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <CampaignProvider>
      <Shell>{children}</Shell>
    </CampaignProvider>
  )
}
