"""Optional LLM layer (CEO-approved, off by default: `enable_llm` in config/engine.yaml).

Providers, all free:
  ollama  - local, no key (default when enable_llm is on): OLLAMA_URL, model from settings
  groq    - GTM_GROQ_API_KEY (free tier)
  gemini  - GTM_GEMINI_API_KEY (free tier)

Rules that keep it honest:
  * Every call gets only text the engine already observed; the prompt forbids outside facts.
  * Structured outputs are validated: any extracted phrase must appear verbatim in the
    source text, or it is dropped. Free-text outputs are labelled "llm:" wherever stored.
  * Every use has a deterministic path that runs without the LLM; failures fall back silently.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

log = logging.getLogger(__name__)


class LLM(Protocol):
    name: str

    async def complete(self, system: str, user: str, *, max_tokens: int = 400) -> str: ...


@dataclass
class OllamaLLM:
    model: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    name: str = "ollama"

    async def complete(self, system: str, user: str, *, max_tokens: int = 400) -> str:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{self.base_url}/api/chat", json={
                "model": self.model, "stream": False, "options": {"temperature": 0, "num_predict": max_tokens},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            })
            r.raise_for_status()
            return r.json()["message"]["content"]


@dataclass
class GroqLLM:
    api_key: str
    model: str = "llama-3.1-8b-instant"
    name: str = "groq"

    async def complete(self, system: str, user: str, *, max_tokens: int = 400) -> str:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             json={"model": self.model, "temperature": 0, "max_tokens": max_tokens,
                                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]


@dataclass
class GeminiLLM:
    api_key: str
    model: str = "gemini-2.0-flash"
    name: str = "gemini"

    async def complete(self, system: str, user: str, *, max_tokens: int = 400) -> str:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}",
                             json={"systemInstruction": {"parts": [{"text": system}]},
                                   "contents": [{"parts": [{"text": user}]}],
                                   "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def build_llm(provider: str = "auto", model: str | None = None) -> LLM | None:
    groq, gemini = os.environ.get("GTM_GROQ_API_KEY"), os.environ.get("GTM_GEMINI_API_KEY")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    if provider in ("ollama", "auto"):
        try:
            httpx.get(f"{ollama_url}/api/tags", timeout=2).raise_for_status()
            return OllamaLLM(model=model or "llama3.2", base_url=ollama_url)
        except httpx.HTTPError:
            if provider == "ollama":
                log.warning("llm: ollama not reachable at %s", ollama_url)
                return None
    if provider in ("groq", "auto") and groq:
        return GroqLLM(groq, model or "llama-3.1-8b-instant")
    if provider in ("gemini", "auto") and gemini:
        return GeminiLLM(gemini, model or "gemini-2.0-flash")
    log.info("llm: no provider available (no local Ollama, no GTM_GROQ_API_KEY / GTM_GEMINI_API_KEY)")
    return None


# ----------------------------------------------------------------------------- guards

_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_json_object(text: str) -> dict | None:
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def grounded(value, source: str) -> bool:
    """A string is grounded when it appears in the source text (case/space-insensitive)."""
    if value is None or value == "":
        return True
    if not isinstance(value, str):
        return False
    norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip()  # noqa: E731
    return norm(value) in norm(source)


def keep_grounded(obj: dict, source: str, fields: tuple[str, ...]) -> dict:
    """Drop any field whose value is not verbatim in the source. Never invents."""
    out = {}
    for k in fields:
        v = obj.get(k)
        if grounded(v, source):
            out[k] = v
    return out
