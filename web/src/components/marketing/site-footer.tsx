import Link from "next/link"
import { Radar } from "lucide-react"

const columns = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "#features" },
      { label: "How it works", href: "#how-it-works" },
      { label: "Sources", href: "#sources" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Sign in", href: "/sign-in" },
      { label: "Get started free", href: "/sign-up" },
    ],
  },
]

export function SiteFooter() {
  return (
    <footer className="border-t bg-card">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div className="max-w-sm">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-8 items-center justify-center rounded-lg bg-brand">
              <Radar className="size-4 text-brand-foreground" />
            </span>
            Qualifyr
          </Link>
          <p className="mt-4 text-sm text-muted-foreground">
            A buyer-only B2B lead engine for Pakistan and the GCC. Finds companies that buy,
            rejects the ones that sell, and explains every score.
          </p>
        </div>

        {columns.map((col) => (
          <div key={col.title}>
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {col.title}
            </h2>
            <ul className="mt-4 flex flex-col gap-2.5">
              {col.links.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t">
        <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted-foreground sm:px-6">
          © {new Date().getFullYear()} Qualifyr. All rights reserved.
        </div>
      </div>
    </footer>
  )
}
