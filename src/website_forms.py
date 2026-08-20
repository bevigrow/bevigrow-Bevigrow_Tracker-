"""
Website contact forms - used when a company publishes no suitable email address.

How it works
    1. Find the contact/enquiry page (the crawler already did this).
    2. Open it in a real browser (Playwright) and read the form fields.
    3. Fill in only fields we can answer truthfully.
    4. Show you the filled form and the exact message BEFORE anything is sent.
    5. Submit only after you approve, and only when TEST_MODE=false.

Hard limits, deliberately:
    * CAPTCHA / "I am not a robot" -> the system STOPS and hands the browser
      to you. It never tries to solve or bypass one.
    * A form is never submitted with a guessed or invented value.
    * If a required field cannot be answered honestly, the form is skipped and
      flagged for you.

Playwright needs a browser the first time:
    python -m playwright install chromium
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.config import OUTBOX_DIR, settings
from src.logging_setup import get_logger
from src.models import PreparedMessage
from src.utils import slugify, write_text

log = get_logger("website_forms")

# What we can honestly answer, in priority order per logical field.
_FIELD_PATTERNS: dict[str, list[str]] = {
    "name": [r"\b(full[\s_-]?name|your[\s_-]?name|name|nom|nombre|naam|navn|nimi)\b",
             r"\b(vorname|firstname|first[\s_-]?name)\b", r"\b(nachname|lastname|surname)\b"],
    "email": [r"\b(e[\s_-]?mail|email|mail|correo|courriel|epost|sahkoposti)\b"],
    "company": [r"\b(company|firm|firma|business|organisation|organization|unternehmen|"
                r"bedrijf|yritys|foretag|société|societa)\b"],
    "phone": [r"\b(phone|tel|telephone|telefon|mobile|handy|puhelin|telefono)\b"],
    "subject": [r"\b(subject|betreff|objet|asunto|oggetto|onderwerp|aihe|amne|topic|reason)\b"],
    "message": [r"\b(message|nachricht|mensaje|messaggio|bericht|viesti|meddelande|"
                r"comment|enquiry|inquiry|anfrage|details|how can we help|your\s+request)\b"],
    "website": [r"\b(website|webseite|url|homepage|site)\b"],
    "country": [r"\b(country|land|pays|pais|paese|maa)\b"],
}

_CAPTCHA_MARKERS = re.compile(
    r"(?i)(recaptcha|hcaptcha|turnstile|cf-challenge|friendly-?captcha|"
    r"i'?m not a robot|ich bin kein roboter|je ne suis pas un robot|captcha)"
)

_CONSENT_PATTERNS = re.compile(
    r"(?i)(privacy|datenschutz|dsgvo|gdpr|terms|agb|consent|einwilligung|accept|zustimm|"
    r"i agree|ich stimme)"
)


@dataclass
class FormField:
    selector: str
    kind: str            # text | textarea | select | checkbox | email | tel
    label: str
    logical: str         # name | email | company | message | ...
    required: bool = False
    value: str = ""
    filled: bool = False


@dataclass
class FormResult:
    ok: bool = False
    submitted: bool = False
    simulated: bool = False
    url: str = ""
    fields: list[FormField] = field(default_factory=list)
    unfilled_required: list[str] = field(default_factory=list)
    captcha_detected: bool = False
    error: str = ""
    preview_file: str = ""
    screenshot: str = ""

    @property
    def status_text(self) -> str:
        if self.captcha_detected:
            return "CAPTCHA - needs you to complete it manually"
        if self.submitted and not self.simulated:
            return "Submitted"
        if self.simulated:
            return "Simulated (nothing submitted)"
        if self.error:
            return f"Failed: {self.error}"
        return "Not submitted"


def _playwright_available() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False, "the 'playwright' package is not installed (pip install -r requirements.txt)"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            path = pw.chromium.executable_path
            if not path or not Path(path).exists():
                return False, "the Chromium browser is not installed (run: python -m playwright install chromium)"
    except Exception as exc:
        return False, str(exc)[:200]
    return True, ""


def our_answers(message: PreparedMessage, company_name: str) -> dict[str, str]:
    """The only values we are ever willing to type into someone's form."""
    return {
        "name": settings.sender_name,
        "email": settings.gmail_sender,
        "company": settings.sender_company or "BeviGrow",
        "phone": settings.sender_phone,
        "subject": message.subject,
        "message": message.body,
        "website": settings.sender_website,
        "country": "India",
    }


def _classify(label: str, name: str, placeholder: str, input_type: str, tag: str) -> str:
    haystack = " ".join(filter(None, [label, name, placeholder])).lower()
    if tag == "textarea":
        return "message"
    if input_type == "email":
        return "email"
    if input_type == "tel":
        return "phone"
    for logical, patterns in _FIELD_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, haystack):
                return logical
    return "unknown"


def prepare_and_submit(
    form_url: str,
    message: PreparedMessage,
    company_name: str,
    submit: bool = False,
    headless: bool | None = None,
) -> FormResult:
    """
    Open the form, fill it, and (only if `submit` is True and the safety
    switches allow it) send it.

    Always writes a readable preview to data/outbox/ first.
    """
    result = FormResult(url=form_url)

    # A preview always exists, even if the browser part fails.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    preview_path = OUTBOX_DIR / f"{stamp}-{slugify(company_name)}-webform.txt"

    available, why = _playwright_available()
    if not available:
        result.error = why
        write_text(
            preview_path,
            f"WEBSITE ENQUIRY - MANUAL (browser automation unavailable: {why})\n"
            f"{'=' * 70}\nForm URL : {form_url}\nCompany  : {company_name}\n"
            f"Subject  : {message.subject}\n{'=' * 70}\n\n{message.body}\n",
        )
        result.preview_file = str(preview_path)
        log.warning("Contact form cannot be automated (%s) - prepared for manual sending.", why)
        return result

    from playwright.sync_api import sync_playwright

    answers = our_answers(message, company_name)
    really_submit = submit and settings.can_send_for_real
    result.simulated = not really_submit
    headless_mode = (not really_submit) if headless is None else headless

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless_mode)
            context = browser.new_context(
                user_agent=settings.user_agent,
                locale="en-GB",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            page.set_default_timeout(settings.http_timeout_seconds * 1000)
            page.goto(form_url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Dismiss an obvious cookie banner so the form is reachable.
            for label in ("Accept all", "Accept", "Alle akzeptieren", "Akzeptieren",
                          "Tout accepter", "Aceptar", "OK", "Got it", "I agree"):
                try:
                    button = page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I))
                    if button.count() > 0 and button.first.is_visible():
                        button.first.click(timeout=3000)
                        page.wait_for_timeout(800)
                        break
                except Exception:
                    continue

            html = page.content()
            if _CAPTCHA_MARKERS.search(html):
                result.captcha_detected = True

            # Find the form that has a textarea (that is the enquiry form).
            forms = page.locator("form")
            target = None
            for i in range(min(forms.count(), 12)):
                candidate = forms.nth(i)
                try:
                    if candidate.locator("textarea").count() > 0:
                        target = candidate
                        break
                except Exception:
                    continue
            if target is None and forms.count() > 0:
                target = forms.first
            if target is None:
                result.error = "No form found on this page."
                browser.close()
                write_text(preview_path, _preview_text(form_url, company_name, message, result))
                result.preview_file = str(preview_path)
                return result

            # --- read and fill the fields --------------------------------
            inputs = target.locator("input, textarea, select")
            for i in range(min(inputs.count(), 40)):
                node = inputs.nth(i)
                try:
                    tag = node.evaluate("el => el.tagName.toLowerCase()")
                    input_type = (node.get_attribute("type") or "").lower()
                    if input_type in {"hidden", "submit", "button", "image", "file", "reset"}:
                        continue
                    if not node.is_visible():
                        continue

                    name = node.get_attribute("name") or node.get_attribute("id") or ""
                    placeholder = node.get_attribute("placeholder") or ""
                    aria = node.get_attribute("aria-label") or ""
                    required = node.get_attribute("required") is not None or \
                        (node.get_attribute("aria-required") or "").lower() == "true"

                    label_text = aria
                    if not label_text and name:
                        try:
                            label = page.locator(f'label[for="{name}"]')
                            if label.count() > 0:
                                label_text = label.first.inner_text()[:80]
                        except Exception:
                            pass

                    logical = _classify(label_text, name, placeholder, input_type, tag)
                    selector = name or f"{tag}#{i}"

                    fld = FormField(
                        selector=selector,
                        kind="textarea" if tag == "textarea" else (input_type or tag),
                        label=(label_text or placeholder or name)[:80],
                        logical=logical,
                        required=required,
                    )

                    if input_type == "checkbox":
                        # Only tick a privacy/terms consent box, nothing else.
                        surrounding = f"{label_text} {name} {placeholder}"
                        if required and _CONSENT_PATTERNS.search(surrounding):
                            node.check(timeout=3000)
                            fld.value = "[checked: consent]"
                            fld.filled = True
                    elif tag == "select":
                        fld.value = "[left at default]"
                    else:
                        value = answers.get(logical, "")
                        if value:
                            node.fill(value, timeout=5000)
                            fld.value = value
                            fld.filled = True

                    if fld.required and not fld.filled and fld.kind != "select":
                        result.unfilled_required.append(fld.label or fld.selector)

                    result.fields.append(fld)
                except Exception as exc:
                    log.debug("Skipped a form field: %s", exc)
                    continue

            shot = OUTBOX_DIR / f"{stamp}-{slugify(company_name)}-form.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                result.screenshot = str(shot)
            except Exception:
                pass

            filled_message = any(f.logical == "message" and f.filled for f in result.fields)
            if not filled_message:
                result.error = "Could not find a message box to put the enquiry in."
            elif result.unfilled_required:
                result.error = (
                    "The form requires fields we cannot answer truthfully: "
                    + ", ".join(result.unfilled_required[:5])
                )
            elif result.captcha_detected:
                result.error = "CAPTCHA present - a human must complete this form."
            else:
                result.ok = True

            # --- submit ---------------------------------------------------
            if result.ok and really_submit:
                clicked = False
                for selector in ('button[type="submit"]', 'input[type="submit"]', "button"):
                    try:
                        button = target.locator(selector)
                        if button.count() > 0 and button.first.is_visible():
                            button.first.click(timeout=8000)
                            clicked = True
                            break
                    except Exception:
                        continue
                if clicked:
                    page.wait_for_timeout(5000)
                    after = page.content()
                    result.submitted = True
                    result.simulated = False
                    if _CAPTCHA_MARKERS.search(after) and "thank" not in after.lower():
                        result.captcha_detected = True
                        result.error = "A CAPTCHA appeared on submit - please finish it manually."
                    try:
                        page.screenshot(path=str(shot).replace(".png", "-after.png"), full_page=True)
                    except Exception:
                        pass
                else:
                    result.error = "Could not find the submit button."
                    result.ok = False

            browser.close()

    except Exception as exc:
        log.exception("Contact form automation failed for %s", form_url)
        result.error = str(exc)[:300]

    write_text(preview_path, _preview_text(form_url, company_name, message, result))
    result.preview_file = str(preview_path)
    return result


def _preview_text(url: str, company: str, message: PreparedMessage, result: FormResult) -> str:
    lines = [
        f"WEBSITE ENQUIRY - {result.status_text}",
        "=" * 70,
        f"Generated : {datetime.now().isoformat(timespec='seconds')}",
        f"Company   : {company}",
        f"Form URL  : {url}",
        f"Subject   : {message.subject}",
        "=" * 70,
        "",
        "FIELDS THE SYSTEM FILLED IN:",
    ]
    for fld in result.fields:
        mark = "x" if fld.filled else " "
        req = " (required)" if fld.required else ""
        value = fld.value if fld.logical != "message" else "[the message below]"
        lines.append(f"  [{mark}] {fld.label or fld.selector}{req}  ->  {value}")
    if result.unfilled_required:
        lines += ["", "REQUIRED FIELDS WE COULD NOT ANSWER:"]
        lines += [f"  - {f}" for f in result.unfilled_required]
    if result.captcha_detected:
        lines += ["", "*** CAPTCHA DETECTED - submit this form manually. ***"]
    lines += ["", "=" * 70, "MESSAGE:", "", message.body, ""]
    return "\n".join(lines)
