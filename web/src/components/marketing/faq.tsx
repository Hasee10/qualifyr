"use client"

import { MessageCircleQuestion } from "lucide-react"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"

const faqs = [
  {
    q: "Can I just sign up?",
    a: "Yes — create an account and you're in. There's no waitlist and no sales call.",
  },
  {
    q: "Where does the company data come from?",
    a: "Free public sources only: OpenStreetMap, Overture Maps, PPRA tenders, the KCCI member directory, GDELT news, and public job/repo APIs like Greenhouse, Lever and GitHub. No paid data broker.",
  },
  {
    q: "How is a lead scored?",
    a: "A deterministic 0–100 score across geography fit, company quality, buyer evidence, contact quality and buying signals — every point comes with a written reason, not a black-box model.",
  },
  {
    q: "Does outreach send automatically?",
    a: "No. Every draft is queued for human approval before it sends, and a durable send ledger prevents any lead from being emailed twice.",
  },
  {
    q: "Is there a mobile app?",
    a: "No — the dashboard is fully responsive, so the same app works on your phone without a separate install.",
  },
]

/** A two-column pairing, not a single centred list: the accordion answers the searchable
 *  questions, the card beside it is for the one question no FAQ ever covers. The
 *  reference's radial ring diagram was considered and dropped deliberately - it is
 *  unusable on mobile (no room for eight orbiting nodes) and hostile to screen readers
 *  (no meaningful DOM order), which a plain accordion does not have to compromise on. */
export function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Frequently asked</h2>
      </div>

      <div className="mt-14 grid gap-10 lg:grid-cols-[2fr_1fr] lg:items-start">
        <Accordion defaultValue={[]}>
          {faqs.map((f) => (
            <AccordionItem key={f.q} value={f.q}>
              <AccordionTrigger className="text-base">{f.q}</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>

        <div className="rounded-xl border border-border/60 bg-card p-6">
          <span className="flex size-10 items-center justify-center rounded-lg bg-brand-muted">
            <MessageCircleQuestion className="size-5 text-brand" />
          </span>
          <h3 className="mt-4 font-heading text-base font-medium">Still stuck?</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Email us directly and we&rsquo;ll get back to you.
          </p>
          <a
            href="mailto:ihaseebarshad10@gmail.com?subject=Qualifyr%20question"
            className="mt-4 inline-block text-sm font-medium text-brand underline-offset-4 hover:underline"
          >
            ihaseebarshad10@gmail.com
          </a>
        </div>
      </div>
    </section>
  )
}
