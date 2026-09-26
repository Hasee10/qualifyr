import { cn } from "@/lib/utils"

/** CSS-only marquee: no JS needed for the scroll, pause-on-hover or the reduced-motion
 *  fallback, so this stays a server component. The track is duplicated once and the
 *  animation shifts exactly -50%, which is what makes the loop seamless. */
// Each source's own domain, used only to fetch its favicon for the marquee. Google's favicon
// service needs no API key and returns a generic icon on a miss (never a 404), so no per-icon
// error handling is needed and this stays a server component.
const sources = [
  { name: "OpenStreetMap", domain: "openstreetmap.org" },
  { name: "Overture Maps", domain: "overturemaps.org" },
  { name: "PPRA tenders", domain: "ppra.org.pk" },
  { name: "KCCI directory", domain: "kcci.com.pk" },
  { name: "GDELT news", domain: "gdeltproject.org" },
  { name: "Greenhouse", domain: "greenhouse.io" },
  { name: "Lever", domain: "lever.co" },
  { name: "GitHub", domain: "github.com" },
]

const favicon = (domain: string) => `https://www.google.com/s2/favicons?domain=${domain}&sz=64`

export function SourceMarquee() {
  return (
    <section id="sources" className="border-y bg-muted/30 py-10">
      <p className="mx-auto max-w-6xl px-4 text-center text-xs font-medium uppercase tracking-wide text-muted-foreground sm:px-6">
        Built on free public sources
      </p>
      <div className="group relative mt-6 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
        <div className="flex w-max animate-marquee gap-10 group-hover:[animation-play-state:paused] motion-reduce:animate-none">
          {[...sources, ...sources].map((s, i) => (
            <span
              key={`${s.name}-${i}`}
              className={cn(
                "flex shrink-0 items-center gap-2.5 whitespace-nowrap text-lg font-semibold text-muted-foreground/70"
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- tiny external favicon, not a Next-optimised asset */}
              <img
                src={favicon(s.domain)}
                alt=""
                aria-hidden="true"
                width={20}
                height={20}
                loading="lazy"
                className="size-5 rounded-sm opacity-80"
              />
              {s.name}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
