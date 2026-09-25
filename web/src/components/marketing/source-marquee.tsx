import { cn } from "@/lib/utils"

/** CSS-only marquee: no JS needed for the scroll, pause-on-hover or the reduced-motion
 *  fallback, so this stays a server component. The track is duplicated once and the
 *  animation shifts exactly -50%, which is what makes the loop seamless. */
const sources = [
  "OpenStreetMap", "Overture Maps", "PPRA tenders", "KCCI directory",
  "GDELT news", "Greenhouse", "Lever", "GitHub",
]

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
              key={`${s}-${i}`}
              className={cn(
                "flex shrink-0 items-center whitespace-nowrap text-lg font-semibold text-muted-foreground/70"
              )}
            >
              {s}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
