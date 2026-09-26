"""The three sanctioned LLM tasks. Each has a deterministic fallback and grounds its
output in the text it was given."""

from __future__ import annotations

import logging

from gtm_engine.llm.client import LLM, keep_grounded, parse_json_object

log = logging.getLogger(__name__)

_NO_OUTSIDE_FACTS = ("Use ONLY the text provided. Do not add, infer or guess anything that is not "
                     "written in it. If a field is not stated, output null.")

REQUIREMENT_FIELDS = ("need", "quantity", "deadline", "location", "budget")
REPLY_LABELS = ("interested", "not_interested", "out_of_office", "wrong_person", "unsubscribe", "auto_reply", "reply")


async def generate_keywords(llm: LLM | None, offer: str, industries: list[str] | None = None,
                            max_keywords: int = 20) -> list[str]:
    """From what the user sells, produce the relevance keywords a candidate's hiring/intent
    text must match to count. This is the P2 fix for the "Imtiaz was hiring, but not for us"
    problem: instead of a hardcoded description, the model derives the terms that make a
    signal relevant to *this* offer (e.g. inventory software -> 'inventory', 'stock', 'erp',
    'point of sale', 'warehouse', 'supply chain').

    Deterministic fallback (no LLM, or a bad response): the offer's own words plus the target
    industries. Output is always lowercased, de-duped and capped, so a caller can trust it as
    a plain keyword list."""
    base = _fallback_keywords(offer, industries)
    if llm is None or not offer.strip():
        return base[:max_keywords]
    system = ("You expand a short product/offer description into the search keywords that "
              "identify a company that would BUY it. Output only a JSON array of short "
              "lowercase keyword strings (1-3 words each), no explanation.")
    user = (f"Offer: {offer!r}\nTarget industries: {industries or []}\n\n"
            f"Return up to {max_keywords} keywords a buyer's job posts, tenders or pages would "
            "contain. Concrete nouns and role/need terms, not marketing words.")
    try:
        raw = await llm.complete(system, user, max_tokens=300)
    except Exception as exc:  # noqa: BLE001 - the LLM is optional
        log.debug("llm keyword generation failed: %s", exc)
        return base[:max_keywords]
    words = _parse_keyword_list(raw)
    merged = _dedupe_lower([*base, *words]) if words else base
    return merged[:max_keywords]


async def judge_intent(llm: LLM | None, offer: str, evidence: str, max_tokens: int = 400) -> dict | None:
    """Decide whether a company is a plausible BUYER of `offer`, judged from `evidence` (its
    own scraped text: name, description, about/services, category, signals) — the CEO's
    "strictly by intent, not keywords" rule. The model must judge NEED, not sector: a company
    in a related industry, or one merely hiring, is not a buyer unless the need is evident.

    Returns {"buyer": bool, "confidence": 0-1, "reason": "<grounded phrase>", "by": "llm:..."}
    or None when there is no LLM, no offer, or no usable evidence — in which case the caller
    keeps the deterministic keyword classifier, so behaviour is unchanged without the LLM.
    This is a judgment, so the reason may paraphrase; it is never treated as an extracted fact."""
    if llm is None or not offer.strip() or not (evidence or "").strip():
        return None
    system = (
        "You decide whether a company is a plausible BUYER of the seller's offer, using ONLY "
        "the company text provided. A company is a buyer only if it plausibly NEEDS and would "
        "purchase the offer for its own use. Being in a related industry, or merely hiring, is "
        "NOT enough on its own — the need must be evident in the text. A company that SELLS or "
        "PROVIDES something similar (an agency, vendor or competitor) is not a buyer. "
        'Answer with one JSON object only: {"buyer": true|false, "confidence": 0.0-1.0, '
        '"reason": "at most 25 words, grounded in the company text"}.'
    )
    user = (f"Seller offer: {offer!r}\n\nCompany text:\n\"\"\"\n{evidence[:4000]}\n\"\"\"\n\n"
            "Judge need, not sector. JSON only.")
    try:
        raw = await llm.complete(system, user, max_tokens=max_tokens)
    except Exception as exc:  # noqa: BLE001 - the LLM is optional
        log.debug("llm intent judgment failed: %s", exc)
        return None
    obj = parse_json_object(raw)
    if not obj or "buyer" not in obj:
        return None
    try:
        confidence = min(max(float(obj.get("confidence", 0.0)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(obj.get("reason") or "").strip().strip('"').replace("\n", " ")[:220]
    return {"buyer": bool(obj["buyer"]), "confidence": confidence, "reason": reason, "by": f"llm:{llm.name}"}


def _fallback_keywords(offer: str, industries: list[str] | None) -> list[str]:
    import re

    stop = {"the", "and", "for", "our", "your", "with", "that", "this", "software", "solution",
            "solutions", "platform", "service", "services", "management", "system", "systems", "tool"}
    words = [w for w in re.findall(r"[a-z]{4,}", (offer or "").lower()) if w not in stop]
    return _dedupe_lower([*(industries or []), *words])


def _parse_keyword_list(raw: str) -> list[str]:
    import json
    import re

    m = re.search(r"\[.*\]", raw or "", re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x) for x in arr]
        except json.JSONDecodeError:
            pass
    # A model that ignored "JSON array" often returns comma/newline-separated terms.
    return [p for p in re.split(r"[,\n]", raw or "") if p.strip()]


def _dedupe_lower(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        t = t.strip().lower().strip("-•*\"' ")
        if t and 1 < len(t) <= 40 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


async def extract_requirement(llm: LLM | None, text: str) -> dict | None:
    """Tender/RFQ text -> {need, quantity, deadline, location, budget}; every value must be a
    verbatim span of `text`. Returns None when the LLM is absent or nothing is grounded."""
    if llm is None or not text or len(text) < 20:
        return None
    system = f"You extract procurement requirements. {_NO_OUTSIDE_FACTS} Answer with one JSON object only."
    user = (f"Text:\n\"\"\"\n{text[:3000]}\n\"\"\"\n\nReturn JSON with keys {list(REQUIREMENT_FIELDS)}. "
            "Each value must be copied exactly from the text (a short span), or null.")
    try:
        raw = await llm.complete(system, user, max_tokens=300)
    except Exception as exc:  # noqa: BLE001 - the LLM is optional
        log.debug("llm extract failed: %s", exc)
        return None
    obj = parse_json_object(raw)
    if not obj:
        return None
    kept = keep_grounded(obj, text, REQUIREMENT_FIELDS)
    kept = {k: v for k, v in kept.items() if v}
    return {**kept, "by": f"llm:{llm.name}"} if kept else None


async def classify_reply(llm: LLM | None, subject: str, body: str) -> str | None:
    """Second opinion only for replies the rules could not label. Returns a label or None."""
    if llm is None or not body.strip():
        return None
    system = ("You label a reply to a cold B2B email. Output exactly one label from: "
              + ", ".join(REPLY_LABELS) + ". Output nothing else.")
    user = f"Subject: {subject}\n\nReply:\n\"\"\"\n{body[:2000]}\n\"\"\""
    try:
        # Reasoning models spend tokens before answering, so the ceiling must leave room.
        raw = (await llm.complete(system, user, max_tokens=256)).strip().lower()
    except Exception as exc:  # noqa: BLE001
        log.debug("llm classify failed: %s", exc)
        return None
    for label in REPLY_LABELS:
        if label in raw:
            return label
    return None


async def draft_hook(llm: LLM | None, company: str, facts: list[str]) -> str | None:
    """One natural sentence from observed facts only. Every fact keyword must survive."""
    if llm is None or not facts:
        return None
    system = f"You write one short, plain sentence for a sales email opener. {_NO_OUTSIDE_FACTS} No flattery, no claims."
    user = f"Company: {company}\nObserved facts:\n- " + "\n- ".join(facts) + "\n\nWrite ONE sentence (max 25 words) that mentions these facts."
    try:
        out = (await llm.complete(system, user, max_tokens=256)).strip()
        lines = [l.strip('" ') for l in out.splitlines() if l.strip()]
        if not lines:
            return None
        sentence = lines[-1]
    except Exception as exc:  # noqa: BLE001
        log.debug("llm hook failed: %s", exc)
        return None
    if len(sentence.split()) > 30 or len(sentence) < 10:
        return None
    low = sentence.lower()
    # Guard: nothing beyond the facts. A sentence that names none of the fact keywords is rejected.
    keywords = {w for f in facts for w in f.lower().split() if len(w) > 4}
    if not any(k in low for k in keywords):
        return None
    return sentence
