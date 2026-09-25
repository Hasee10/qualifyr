"use client"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"

const faqs = [
  {
    q: "Is this multi-tenant — can my team sign up?",
    a: "Not yet. Every account today is a single operator, provisioned by hand. There is no self-serve signup; use \"Request access\" and we'll set one up.",
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

export function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-3xl px-4 py-24 sm:px-6">
      <div className="text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Frequently asked</h2>
      </div>

      <Accordion className="mt-10" defaultValue={[]}>
        {faqs.map((f) => (
          <AccordionItem key={f.q} value={f.q}>
            <AccordionTrigger className="text-base">{f.q}</AccordionTrigger>
            <AccordionContent className="text-muted-foreground">{f.a}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  )
}
