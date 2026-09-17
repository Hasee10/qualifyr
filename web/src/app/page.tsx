"use client"

import * as React from "react"
import {
  LayoutDashboard,
  Users,
  ShoppingCart,
  FileText,
  Settings,
  Bell,
  Search,
  TrendingUp,
  DollarSign,
  UserPlus,
  Clock,
  Moon,
  Sun,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from "@/components/ui/chart"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"

const sidebarNavItems = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/" },
  { icon: Users, label: "Customers", href: "/customers" },
  { icon: ShoppingCart, label: "Deals", href: "/deals" },
  { icon: FileText, label: "Reports", href: "/reports" },
  { icon: Settings, label: "Settings", href: "/settings" },
]

const statCards = [
  {
    title: "Total Revenue",
    value: "$124,563",
    change: "+12.5%",
    trend: "up",
    icon: DollarSign,
  },
  {
    title: "New Customers",
    value: "2,847",
    change: "+8.2%",
    trend: "up",
    icon: UserPlus,
  },
  {
    title: "Pending Deals",
    value: "156",
    change: "-3.1%",
    trend: "down",
    icon: Clock,
  },
  {
    title: "Conversion Rate",
    value: "24.6%",
    change: "+4.3%",
    trend: "up",
    icon: TrendingUp,
  },
]

const revenueChartData = [
  { month: "Jan", revenue: 45000, deals: 28 },
  { month: "Feb", revenue: 52000, deals: 35 },
  { month: "Mar", revenue: 48000, deals: 31 },
  { month: "Apr", revenue: 61000, deals: 42 },
  { month: "May", revenue: 55000, deals: 38 },
  { month: "Jun", revenue: 67000, deals: 45 },
]

const chartConfig = {
  revenue: {
    label: "Revenue",
    theme: {
      light: "var(--chart-1)",
      dark: "var(--chart-1)",
    },
  },
  deals: {
    label: "Deals",
    theme: {
      light: "var(--chart-2)",
      dark: "var(--chart-2)",
    },
  },
}

const recentDeals = [
  {
    id: "DEAL-001",
    customer: "Acme Corp",
    contact: "Sarah Johnson",
    email: "sarah@acmecorp.com",
    value: "$45,000",
    status: "Won",
    progress: 100,
  },
  {
    id: "DEAL-002",
    customer: "TechStart Inc",
    contact: "Michael Chen",
    email: "m.chen@techstart.io",
    value: "$28,500",
    status: "Negotiation",
    progress: 75,
  },
  {
    id: "DEAL-003",
    customer: "Global Solutions",
    contact: "Emma Williams",
    email: "emma@globalsol.com",
    value: "$67,000",
    status: "Proposal",
    progress: 50,
  },
  {
    id: "DEAL-004",
    customer: "NextGen Labs",
    contact: "David Park",
    email: "d.park@nextgenlabs.tech",
    value: "$34,200",
    status: "Qualified",
    progress: 25,
  },
  {
    id: "DEAL-005",
    customer: "Innovate Co",
    contact: "Lisa Martinez",
    email: "lisa@innovate.co",
    value: "$52,800",
    status: "Won",
    progress: 100,
  },
]

const topCustomers = [
  { name: "Acme Corporation", initials: "AC", revenue: "$245,000", deals: 12 },
  { name: "TechStart Inc", initials: "TS", revenue: "$189,500", deals: 8 },
  { name: "Global Solutions Ltd", initials: "GS", revenue: "$156,200", deals: 6 },
  { name: "NextGen Labs", initials: "NG", revenue: "$98,400", deals: 5 },
  { name: "Innovate Partners", initials: "IP", revenue: "$87,300", deals: 4 },
]

function StatCard({
  title,
  value,
  change,
  trend,
  icon: Icon,
}: (typeof statCards)[0]) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardDescription className="text-muted-foreground">
          {title}
        </CardDescription>
        <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
          <Icon className="size-5 text-muted-foreground" data-icon="inline-start" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold">{value}</span>
          <Badge
            variant={trend === "up" ? "default" : "destructive"}
            className="text-xs"
          >
            {change}
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}

function RevenueChart() {
  return (
    <Card className="col-span-1 lg:col-span-2">
      <CardHeader>
        <CardTitle>Revenue Overview</CardTitle>
        <CardDescription>Monthly revenue and deals for 2024</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={revenueChartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="month" className="text-xs" />
              <YAxis className="text-xs" />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar dataKey="revenue" fill="var(--color-revenue)" name="Revenue" radius={[4, 4, 0, 0]} />
              <Bar dataKey="deals" fill="var(--color-deals)" name="Deals" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

function DealsTable() {
  return (
    <Card className="col-span-1 lg:col-span-3">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Recent Deals</CardTitle>
            <CardDescription>Latest deals and their status</CardDescription>
          </div>
          <Button variant="outline" size="sm">
            View All
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Deal ID</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Progress</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {recentDeals.map((deal) => (
              <TableRow key={deal.id}>
                <TableCell className="font-medium">{deal.id}</TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">{deal.customer}</span>
                    <span className="text-xs text-muted-foreground">
                      {deal.contact}
                    </span>
                  </div>
                </TableCell>
                <TableCell>{deal.value}</TableCell>
                <TableCell>
                  <Badge
                    variant={
                      deal.status === "Won"
                        ? "default"
                        : deal.status === "Negotiation"
                          ? "secondary"
                          : "outline"
                    }
                  >
                    {deal.status}
                  </Badge>
                </TableCell>
                <TableCell className="w-[150px]">
                  <div className="flex items-center gap-2">
                    <Progress value={deal.progress} className="h-2" />
                    <span className="text-xs text-muted-foreground">
                      {deal.progress}%
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function TopCustomers() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Customers</CardTitle>
        <CardDescription>By total revenue</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          {topCustomers.map((customer) => (
            <div key={customer.name} className="flex items-center gap-3">
              <Avatar className="size-9">
                <AvatarFallback>{customer.initials}</AvatarFallback>
              </Avatar>
              <div className="flex flex-1 items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-sm font-medium">{customer.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {customer.deals} deals
                  </span>
                </div>
                <span className="font-medium">{customer.revenue}</span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function SidebarContent({
  darkMode,
  onToggleDarkMode,
}: {
  darkMode: boolean
  onToggleDarkMode: () => void
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-6">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary">
          <LayoutDashboard
            className="size-5 text-primary-foreground"
            data-icon="inline-start"
          />
        </div>
        <span className="text-lg font-semibold">CRM Dashboard</span>
      </div>
      <Separator />
      <nav className="flex-1 overflow-y-auto px-4 py-4">
        <div className="flex flex-col gap-1">
          {sidebarNavItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="inline-flex shrink-0 items-center justify-start gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground"
            >
              <item.icon
                className="size-4"
                data-icon="inline-start"
              />
              {item.label}
            </a>
          ))}
        </div>
      </nav>
      <Separator />
      <div className="p-4">
        <button
          onClick={onToggleDarkMode}
          className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground cursor-pointer"
        >
          <Avatar className="size-9">
            <AvatarFallback>JD</AvatarFallback>
          </Avatar>
          <div className="flex flex-1 flex-col">
            <span className="text-sm font-medium">John Doe</span>
            <span className="text-xs text-muted-foreground">
              {darkMode ? "Dark Mode" : "Light Mode"}
            </span>
          </div>
          {darkMode ? (
            <Sun className="size-4" data-icon="inline-end" />
          ) : (
            <Moon className="size-4" data-icon="inline-end" />
          )}
        </button>
      </div>
    </div>
  )
}

function MobileSidebar({
  darkMode,
  onToggleDarkMode,
}: {
  darkMode: boolean
  onToggleDarkMode: () => void
}) {
  const [open, setOpen] = React.useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger>
        <div
          role="button"
          tabIndex={0}
          className="inline-flex shrink-0 items-center justify-center rounded-lg px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground cursor-pointer"
          onClick={() => setOpen(true)}
          onKeyDown={(e) => e.key === "Enter" && setOpen(true)}
        >
          <LayoutDashboard className="size-5" data-icon="inline-start" />
          <span className="sr-only">Toggle sidebar</span>
        </div>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-0">
        <SheetHeader className="sr-only">
          <SheetTitle>Navigation</SheetTitle>
        </SheetHeader>
        <SidebarContent darkMode={darkMode} onToggleDarkMode={onToggleDarkMode} />
      </SheetContent>
    </Sheet>
  )
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = React.useState("overview")
  const [darkMode, setDarkMode] = React.useState(false)

  React.useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, [darkMode])

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 flex-col border-r bg-card lg:flex">
        <SidebarContent darkMode={darkMode} onToggleDarkMode={() => setDarkMode(!darkMode)} />
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b bg-card px-6">
          <MobileSidebar darkMode={darkMode} onToggleDarkMode={() => setDarkMode(!darkMode)} />
          <div className="flex flex-1 items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search
                className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                data-icon="inline-start"
              />
              <Input
                placeholder="Search customers, deals..."
                className="pl-9"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
            >
              {darkMode ? (
                <Sun className="size-5" data-icon="inline-start" />
              ) : (
                <Moon className="size-5" data-icon="inline-start" />
              )}
              <span className="sr-only">Toggle dark mode</span>
            </Button>
            <Button variant="ghost" size="icon">
              <Bell className="size-5" data-icon="inline-start" />
              <span className="sr-only">Notifications</span>
            </Button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <div className="mb-6">
            <h1 className="text-2xl font-bold">Dashboard</h1>
            <p className="text-muted-foreground">
              Welcome back! Here&apos;s your sales overview.
            </p>
          </div>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="analytics">Analytics</TabsTrigger>
              <TabsTrigger value="reports">Reports</TabsTrigger>
            </TabsList>
<TabsContent value={activeTab} className="mt-6">
            <div className="grid gap-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {statCards.map((stat) => (
                  <StatCard key={stat.title} {...stat} />
                ))}
              </div>
              <div className="grid gap-6 lg:grid-cols-3">
                <RevenueChart />
                <TopCustomers />
              </div>
              <div className="grid gap-6 lg:grid-cols-3">
                <DealsTable />
              </div>
            </div>
          </TabsContent>
</Tabs>
</main>
</div>
</div>
)
}