"""
BeviGrow tracker integration.

Your tracker at
    https://bevigrow-frontend-dkay.onrender.com/app/outreach
is a React front-end talking to a FastAPI backend at
    https://bevigrow-backend-dkay.onrender.com

The backend publishes a full OpenAPI spec, so this is a proper API
integration - no browser automation needed.

DISCOVERED API CONTRACT
-----------------------
Auth      POST /api/auth/login        {"email": ..., "password": ...}
                                      -> {"access_token": "...", "user": {...}}
          All other calls send        Authorization: Bearer <access_token>

Create    POST   /api/outreach                       -> 201 OutreachOut
Read      GET    /api/outreach?search=&status=&due=  -> [OutreachOut]
          GET    /api/outreach/{id}                  -> OutreachOut
Update    PATCH  /api/outreach/{id}                  -> OutreachOut
Follow-up POST   /api/outreach/{id}/follow-up?days_until_next=N
Stats     GET    /api/outreach/stats

FIELD MAPPING (tracker form label -> API field)
    Company                 -> company_name
    Contact person          -> contact_person
    Website                 -> website
    Country                 -> country
    Channel                 -> contact_method   (email | linkedin | website_form |
                                                 instagram | phone | whatsapp | other)
    Exact place             -> contact_point    (inbox / LinkedIn URL / form URL)
    Email                   -> email
    Date contacted          -> contacted_on     (YYYY-MM-DD)
    Message we sent         -> message_sent     (the EXACT text that was sent)
    Their reply             -> their_reply
    Status                  -> status           (follow_up_needed | follow_up_sent |
                                                 waiting_reply | replied | no_response |
                                                 not_interested)
    Date they replied       -> replied_on
    Our next action         -> next_action
    Next follow-up date     -> next_follow_up
    Notes / memory          -> notes
"""

from __future__ import annotations

import time
from typing import Any

import requests

from src.config import STATE_DIR, settings
from src.logging_setup import get_logger
from src.models import Channel, PreparedMessage, ResearchResult, TrackerStatus
from src.utils import http_session, read_json, write_json

log = get_logger("tracker")

TOKEN_CACHE = STATE_DIR / "tracker_token.json"


class TrackerError(RuntimeError):
    pass


class TrackerClient:
    """Thin, typed client for the BeviGrow outreach API."""

    def __init__(self, base_url: str | None = None):
        self.base = (base_url or settings.bevigrow_api_base).rstrip("/")
        self.session = http_session()
        self._token: str = ""
        self._user: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def _load_cached_token(self) -> bool:
        cached = read_json(TOKEN_CACHE) or {}
        if cached.get("base") != self.base or cached.get("email") != settings.bevigrow_email:
            return False
        # Tokens are typically valid for hours; re-use for 6 h then re-login.
        if time.time() - cached.get("obtained_at", 0) > 6 * 3600:
            return False
        self._token = cached.get("access_token", "")
        self._user = cached.get("user", {})
        return bool(self._token)

    def login(self, force: bool = False) -> dict[str, Any]:
        """Log in and cache the bearer token. Returns the user record."""
        if not settings.tracker_configured:
            raise TrackerError(
                "BeviGrow tracker credentials are missing. Set BEVIGROW_EMAIL and "
                "BEVIGROW_PASSWORD in your .env file."
            )
        if not force and self._load_cached_token():
            return self._user

        try:
            resp = self.session.post(
                f"{self.base}/api/auth/login",
                json={"email": settings.bevigrow_email, "password": settings.bevigrow_password},
                timeout=settings.http_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise TrackerError(f"Could not reach the BeviGrow backend: {exc}") from exc

        if resp.status_code in (400, 401, 403):
            raise TrackerError(
                "BeviGrow login rejected. Check BEVIGROW_EMAIL / BEVIGROW_PASSWORD in .env."
            )
        if resp.status_code >= 400:
            raise TrackerError(f"BeviGrow login failed: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        self._token = data.get("access_token", "")
        self._user = data.get("user", {}) or {}
        if not self._token:
            raise TrackerError("BeviGrow login returned no access token.")

        write_json(
            TOKEN_CACHE,
            {
                "base": self.base,
                "email": settings.bevigrow_email,
                "access_token": self._token,
                "user": self._user,
                "obtained_at": time.time(),
            },
        )
        log.info("Signed in to BeviGrow tracker as %s", self._user.get("name") or self._user.get("email"))
        return self._user

    @property
    def user(self) -> dict[str, Any]:
        if not self._user:
            self.login()
        return self._user

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self.login()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, *, params: dict | None = None,
                 json_body: dict | None = None, retry_auth: bool = True) -> Any:
        url = f"{self.base}{path}"
        try:
            resp = self.session.request(
                method, url, headers=self._headers(), params=params, json=json_body,
                timeout=settings.http_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise TrackerError(f"{method} {path} failed: {exc}") from exc

        if resp.status_code == 401 and retry_auth:
            log.info("Tracker token expired - signing in again.")
            self.login(force=True)
            return self._request(method, path, params=params, json_body=json_body,
                                 retry_auth=False)

        if resp.status_code == 422:
            raise TrackerError(f"Tracker rejected the data ({path}): {resp.text[:500]}")
        if resp.status_code >= 400:
            raise TrackerError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")

        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # ------------------------------------------------------------------
    # Outreach records
    # ------------------------------------------------------------------
    def health(self) -> dict:
        resp = self.session.get(f"{self.base}/api/health", timeout=settings.http_timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def list_outreach(self, search: str | None = None, status: str | None = None,
                      country: str | None = None, due: bool = False,
                      limit: int = 300) -> list[dict]:
        params: dict[str, Any] = {"limit": min(max(limit, 1), 500)}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        if country:
            params["country"] = country
        if due:
            params["due"] = True
        data = self._request("GET", "/api/outreach", params=params)
        return data if isinstance(data, list) else data.get("items", [])

    def get_outreach(self, record_id: int) -> dict:
        return self._request("GET", f"/api/outreach/{record_id}")

    def create_outreach(self, payload: dict) -> dict:
        clean = {k: v for k, v in payload.items() if v not in (None, "", [])}
        if not clean.get("company_name"):
            raise TrackerError("Cannot create a tracker record without a company name.")
        record = self._request("POST", "/api/outreach", json_body=clean)
        log.info("Tracker record #%s created for %s", record.get("id"), record.get("company_name"))
        return record

    def update_outreach(self, record_id: int, patch: dict) -> dict:
        clean = {k: v for k, v in patch.items() if v is not None}
        return self._request("PATCH", f"/api/outreach/{record_id}", json_body=clean)

    def log_follow_up(self, record_id: int, days_until_next: int | None = None) -> dict:
        days = days_until_next or settings.follow_up_days
        days = min(max(days, 1), 90)
        return self._request(
            "POST", f"/api/outreach/{record_id}/follow-up", params={"days_until_next": days}
        )

    def stats(self) -> dict:
        return self._request("GET", "/api/outreach/stats")

    def due_follow_ups(self, limit: int = 200) -> list[dict]:
        return self.list_outreach(due=True, limit=limit)


# --------------------------------------------------------------------------
# Building the payload from a pipeline result
# --------------------------------------------------------------------------
def build_outreach_payload(
    result: ResearchResult,
    message: PreparedMessage,
    contact_person: str = "",
    status: TrackerStatus = TrackerStatus.WAITING_REPLY,
    contacted_on: str = "",
    next_action: str = "",
    next_follow_up: str = "",
    notes: str = "",
    owner_id: int | None = None,
) -> dict:
    """Map our internal objects onto the tracker's API fields."""
    channel = message.channel

    if channel is Channel.EMAIL:
        # "Exact place" records every inbox the message actually went to.
        contact_point = ", ".join(message.to + message.cc) or message.target_url
        email = message.to[0] if message.to else ""
    elif channel is Channel.LINKEDIN:
        contact_point = message.target_url
        email = result.primary_email.address if result.primary_email else ""
    elif channel is Channel.WEBSITE_FORM:
        contact_point = message.target_url
        email = ""
    else:
        contact_point = message.target_url
        email = ""

    # "Message we sent" must hold the EXACT text that went out.
    if channel is Channel.EMAIL:
        header = f"Subject: {message.subject}\nTo: {', '.join(message.to)}"
        if message.cc:
            header += f"\nCc: {', '.join(message.cc)}"
        message_sent = f"{header}\n\n{message.body}"
    else:
        message_sent = message.body

    return {
        "company_name": result.resolved_company_name[:200],
        "contact_person": contact_person or None,
        "website": (result.website or "")[:300] or None,
        "email": (email or "")[:255] or None,
        "country": (result.country or "")[:100] or None,
        "contact_method": channel.value,
        "contact_point": (contact_point or "")[:300] or None,
        "contacted_on": contacted_on or None,
        "message_sent": message_sent,
        "status": status.value,
        "next_action": next_action or None,
        "next_follow_up": next_follow_up or None,
        "notes": notes or None,
        "owner_id": owner_id,
    }


def build_notes(result: ResearchResult, email_notes: str, extra: list[str] | None = None) -> str:
    """
    The 'Notes / memory' field - short and useful for the next contact attempt.
    Deliberately NOT a dump of the whole research.
    """
    parts: list[str] = []
    if email_notes:
        parts.append(email_notes)

    person = result.people[0] if result.people else None
    if person:
        title = f", {person.title}" if person.title else ""
        parts.append(f"Contact: {person.name}{title}.")
    else:
        parts.append("No named contact person verified publicly.")

    if result.linkedin_company_url:
        parts.append(f"LinkedIn: {result.linkedin_company_url}")
    if result.contact_form_url:
        parts.append(f"Contact form: {result.contact_form_url}")

    parts.append(f"Relevance: {result.relevance.priority.value}.")

    for item in (extra or []):
        if item:
            parts.append(item)

    for warning in result.warnings[:2]:
        parts.append(f"Note: {warning}")

    text = " ".join(p.strip() for p in parts if p and p.strip())
    return text[:1800]


_client: TrackerClient | None = None


def get_client() -> TrackerClient:
    global _client
    if _client is None:
        _client = TrackerClient()
    return _client
