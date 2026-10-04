/** CSS-only marquee: no JS needed for the scroll, pause-on-hover or the reduced-motion
 *  fallback, so this stays a server component. The track is duplicated once and the
 *  animation shifts exactly -50%, which is what makes the loop seamless. */
// Each source's own domain, used only to fetch its logo for the marquee. Google's favicon
// service needs no API key and returns a generic icon on a miss (never a 404), so no per-icon
// error handling is needed and this stays a server component. Logo-only: the name lives in
// alt/title for screen readers and hover, but is not drawn, so sz=128 keeps the mark crisp.
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

const favicon = (domain: string) => `https://www.google.com/s2/favicons?domain=${domain}&sz=128`

export function SourceMarquee() {
  return (
    <section id="sources" className="border-y bg-muted/30 py-12">
      <p className="mx-auto max-w-6xl px-4 text-center text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground sm:px-6">
        Built on free public sources
      </p>
      <div className="group relative mt-8 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
        <div className="flex w-max animate-marquee items-center gap-5 group-hover:[animation-play-state:paused] motion-reduce:animate-none sm:gap-7">
          {[...sources, ...sources].map((s, i) => (
            <span
              key={`${s.name}-${i}`}
              title={s.name}
              aria-label={s.name}
              // A white tile keeps every logo legible: favicons are drawn for light backgrounds,
              // so dark marks (OpenStreetMap, PPRA, KCCI) would vanish on a dark chip. This reads
              // as a consistent "app-icon" wall in both themes.
              className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-black/5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- tiny external favicon, not a Next-optimised asset */}
              <img
                src={favicon(s.domain)}
                alt={s.name}
                width={36}
                height={36}
                loading="lazy"
                className="size-9 object-contain"
              />
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
