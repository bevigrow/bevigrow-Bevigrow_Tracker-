"""Pluggable text-generation backends.

Two providers are supported, chosen by whichever API key is configured:

  * **Google Gemini** — has a genuinely free tier (no card required), which is
    why it is the default when both keys are present.
  * **Anthropic Claude Haiku** — paid, but cheap and slightly better at terse
    business prose.

Both are optional. With neither configured the caller falls back to
deterministic local logic, so the product never depends on an AI being
available.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings

log = logging.getLogger("bevigrow.ai")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ProviderError(Exception):
    """A provider was configured but could not produce a completion."""


def active_provider() -> str | None:
    """Which backend will actually be used: 'gemini', 'anthropic', or None."""
    if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY.strip():
        return "gemini"
    if settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY.strip():
        return "anthropic"
    if settings.AI_PROVIDER == "auto":
        # Prefer the free one.
        if settings.GEMINI_API_KEY.strip():
            return "gemini"
        if settings.ANTHROPIC_API_KEY.strip():
            return "anthropic"
    return None


def active_model() -> str:
    provider = active_provider()
    if provider == "gemini":
        return settings.GEMINI_MODEL
    if provider == "anthropic":
        return settings.AI_MODEL
    return "rule-based"


# ------------------------------------------------------------------ gemini


def _gemini(prompt: str, system: str, max_tokens: int) -> str:
    url = GEMINI_URL.format(model=settings.GEMINI_MODEL)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {
            # gemini-flash-latest reasons before answering and charges those
            # thinking tokens against maxOutputTokens, which truncated
            # summaries mid-sentence. Disabling thinking is rejected by this
            # model (400), so the budget is widened instead — the visible
            # answer stays short because the prompt asks for it.
            "maxOutputTokens": max(max_tokens * 4, 2048),
            "temperature": 0.4,
        },
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Key goes in the header, not the query string: it is Google's
            # documented form, it works with both the AIza… and newer AQ.…
            # key formats, and it keeps the secret out of URLs and access logs.
            res = client.post(
                url,
                headers={"X-goog-api-key": settings.GEMINI_API_KEY.strip()},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ProviderError(f"Could not reach Gemini: {exc}") from exc

    if res.status_code == 429:
        raise ProviderError(
            "Gemini free-tier quota exhausted for "
            f"{settings.GEMINI_MODEL}. It resets daily; using the built-in "
            "summaries until then."
        )
    if res.status_code != 200:
        # Surface the reason at WARNING so a bad key or exhausted quota is
        # visible in the logs rather than silently degrading forever.
        raise ProviderError(f"Gemini returned {res.status_code}: {res.text[:200]}")

    data = res.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ProviderError(f"Gemini returned no candidates: {str(data)[:200]}")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise ProviderError("Gemini returned an empty completion")
    return text


# --------------------------------------------------------------- anthropic


def _anthropic(prompt: str, system: str, max_tokens: int) -> str:
    # Imported lazily so the package is only needed when actually used.
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY.strip())
    try:
        message = client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 - normalise to one error type
        raise ProviderError(f"Anthropic request failed: {exc}") from exc

    text = "\n".join(b.text for b in message.content if b.type == "text").strip()
    if not text:
        raise ProviderError("Anthropic returned an empty completion")
    return text


# ------------------------------------------------------------------ public


def key_fingerprint(raw: str) -> str:
    """Enough of a key to recognise it, never enough to use it.

    The prefix is the useful part: a Gemini API key starts "AIza", whereas an
    OAuth token starts "AQ." and the API rejects it. Telling those apart
    without printing the secret is the whole point.
    """
    key = raw.strip()
    if not key:
        return "not set"
    return f"{key[:4]}… ({len(key)} chars)"


def probe(provider: str) -> str:
    """Make the smallest real call and report what actually happened.

    `complete()` deliberately swallows provider errors so a dead API key can
    never break a page. That is right for users and useless for whoever has to
    fix the key, so this path re-raises the detail instead.
    """
    try:
        if provider == "gemini":
            _gemini("Reply with the single word: ok", "You are a connectivity probe.", 16)
        elif provider == "anthropic":
            _anthropic("Reply with the single word: ok", "You are a connectivity probe.", 16)
        else:
            return "no provider configured"
    except ProviderError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"Unexpected {type(exc).__name__}: {exc}"
    return "ok"


def complete(prompt: str, system: str, max_tokens: int) -> str | None:
    """Generate text, or return None so the caller can use its fallback."""
    provider = active_provider()
    if provider is None:
        return None
    try:
        if provider == "gemini":
            return _gemini(prompt, system, max_tokens)
        return _anthropic(prompt, system, max_tokens)
    except ProviderError as exc:
        log.warning("%s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 - never let AI break a request
        log.warning("Unexpected AI failure (%s): %s", provider, exc)
        return None
