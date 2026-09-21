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
        raw = (await llm.complete(system, user, max_tokens=10)).strip().lower()
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
        sentence = (await llm.complete(system, user, max_tokens=60)).strip().splitlines()[0].strip('" ')
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
