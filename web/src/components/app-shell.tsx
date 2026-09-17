"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, Users, Send, Radar, Moon, Sun, Menu } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import { CampaignProvider, useCampaign } from "@/components/campaign-context"

const nav = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/" },
  { icon: Radar, label: "Campaigns", href: "/campaigns" },
  { icon: Users, label: "Leads", href: "/leads" },
  { icon: Send, label: "Outreach", href: "/outreach" },
]

function SidebarContent() {
  const pathname = usePathname()
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-6">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary">
          <Radar className="size-5 text-primary-foreground" />
        </div>
        <div className="flex flex-col">
          <span className="text-lg font-semibold leading-tight">Qualifyr</span>
          <span className="text-xs text-muted-foreground">buyer-only lead engine</span>
        </div>
      </div>
      <Separator />
      <nav className="flex-1 overflow-y-auto px-4 py-4">
        <div className="flex flex-col gap-1">
          {nav.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "inline-flex shrink-0 items-center justify-start gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground",
                  active && "bg-muted text-foreground"
                )}
              >
                <item.icon className="size-4" />
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
  const [health, setHealth] = React.useState<{ smtp_configured: boolean; require_approval: boolean } | null | "down">(null)
  React.useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth("down"))
  }, [])
  return (
    <div className="flex flex-col gap-1 p-4 text-xs text-muted-foreground">
      {health === "down" ? (
        <Badge variant="destructive">API offline</Badge>
      ) : health ? (
        <>
          <span>API connected</span>
          <span>Sending: {health.smtp_configured ? "Gmail configured" : "dry-run (no credentials)"}</span>
          <span>Approval: {health.require_approval ? "required" : "off"}</span>
        </>
      ) : (
        <span>Connecting…</span>
      )}
    </div>
  )
}

function CampaignPicker() {
  const { campaigns, campaignId, setCampaignId } = useCampaign()
  if (campaigns.length <= 1) {
    return <span className="text-sm text-muted-foreground">{campaigns[0]?.name ?? "No campaigns"}</span>
  }
  return (
    <select
      className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
      value={campaignId ?? ""}
      onChange={(e) => setCampaignId(e.target.value)}
    >
      {campaigns.map((c) => (
        <option key={c.campaign_id} value={c.campaign_id}>{c.name}</option>
      ))}
    </select>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  const [darkMode, setDarkMode] = React.useState(false)
  const [open, setOpen] = React.useState(false)
  React.useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode)
  }, [darkMode])

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 flex-col border-r bg-card lg:flex">
        <SidebarContent />
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
            <span className="text-xs uppercase tracking-wide text-muted-foreground">Campaign</span>
            <CampaignPicker />
          </div>
          <Button variant="ghost" size="icon" onClick={() => setDarkMode(!darkMode)}>
            {darkMode ? <Sun className="size-5" /> : <Moon className="size-5" />}
            <span className="sr-only">Toggle dark mode</span>
          </Button>
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
