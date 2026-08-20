"""
The setup wizard - so you never have to hand-edit a configuration file.

    python -m src.main setup

Asks for each value one at a time, explains what it is, hides passwords while
you type, writes them into .env, and then immediately tests whatever it can
(tracker login, Claude key, Gmail).

Nothing is printed back to the screen or written to a log once entered.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.panel import Panel
from rich.prompt import Prompt

from src.config import ENV_FILE, ROOT
from src.logging_setup import console

# (key, question, help text, secret?, required?)
_QUESTIONS: list[tuple[str, str, str, bool, bool]] = [
    ("SENDER_NAME", "Your full name",
     "Goes at the bottom of every email, and in 'From: Your Name <your@email>'.",
     False, True),
    ("SENDER_TITLE", "Your job title",
     "For example: Export Manager, Director, Founder.", False, False),
    ("SENDER_PHONE", "Your phone number (with country code)",
     "Leave blank to keep it out of the signature.", False, False),
    ("SENDER_WEBSITE", "BeviGrow website",
     "Leave blank if you do not have one yet - the line is simply omitted.",
     False, False),
    ("GMAIL_SENDER", "The Gmail address you send outreach FROM",
     "This must be the same account you authorise in the next step.", False, True),
    ("OUTREACH_BCC", "BCC every outreach to this address (optional)",
     "Useful if you want a copy in a second mailbox.", False, False),
    ("BEVIGROW_EMAIL", "Your BeviGrow tracker login email",
     "The email you use at bevigrow-frontend-dkay.onrender.com.", False, True),
    ("BEVIGROW_PASSWORD", "Your BeviGrow tracker password",
     "Stored only in .env on this computer, never printed or logged.", True, True),
    ("ANTHROPIC_API_KEY", "Anthropic API key (optional, recommended)",
     "From console.anthropic.com. NOTE: a Claude subscription is not an API key - "
     "API access is billed separately. Without it, research falls back to keyword rules.",
     True, False),
    ("TAVILY_API_KEY", "Tavily search API key (optional)",
     "Free tier at tavily.com. Makes finding official websites much more reliable.",
     True, False),
]


def _read_env_lines() -> list[str]:
    if ENV_FILE.exists():
        return ENV_FILE.read_text(encoding="utf-8").splitlines()
    example = ROOT / ".env.example"
    if example.exists():
        return example.read_text(encoding="utf-8").splitlines()
    return []


def _current_value(lines: list[str], key: str) -> str:
    for line in lines:
        match = re.match(rf"^\s*{re.escape(key)}\s*=\s*(.*)$", line)
        if match:
            return match.group(1).strip().strip('"').strip("'")
    return ""


def _set_value(lines: list[str], key: str, value: str) -> list[str]:
    """Replace the value in place, preserving all comments and ordering."""
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


def _mask(value: str) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-2:]}"


def run() -> int:
    console.print(
        Panel(
            "This writes your settings into the .env file.\n"
            "Press Enter to keep what is already there. Passwords are hidden while you type\n"
            "and are never shown again or written to a log.",
            title="BeviGrow outreach setup", border_style="cyan",
        )
    )

    lines = _read_env_lines()

    for key, question, helptext, secret, required in _QUESTIONS:
        current = _current_value(lines, key)
        console.print(f"\n[bold]{question}[/bold]")
        console.print(f"[dim]{helptext}[/dim]")
        if current:
            shown = _mask(current) if secret else current
            console.print(f"[dim]currently: {shown}[/dim]")

        while True:
            answer = Prompt.ask("  >", password=secret, default="", show_default=False)
            answer = answer.strip()
            if not answer:
                if current or not required:
                    break  # keep what is there / leave optional blank
                console.print("  [yellow]This one is required.[/yellow]")
                continue
            lines = _set_value(lines, key, answer)
            break

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass
    console.print(f"\n[green]Saved to {ENV_FILE}[/green]")

    _verify()

    console.print(
        Panel(
            "Next steps:\n"
            "  1. Put your approved email sample into config\\email_template.md\n"
            "  2. python -m src.main auth-gmail        (one browser window, once)\n"
            "  3. python -m src.main check             (should be all green)\n"
            "  4. python -m src.main run --limit 1     (safe: TEST_MODE is still on)",
            title="What to do now", border_style="green",
        )
    )
    return 0


def _verify() -> None:
    """Test everything we can, immediately, so problems surface here and not later."""
    # The settings object was built at import time, so re-read the file.
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE, override=True)

    import importlib

    from src import config as config_mod

    importlib.reload(config_mod)

    console.print("\n[bold]Checking what you just entered...[/bold]")

    # --- tracker ---
    email = config_mod._str("BEVIGROW_EMAIL")
    password = config_mod._str("BEVIGROW_PASSWORD")
    if email and password:
        try:
            import requests

            base = config_mod._str(
                "BEVIGROW_API_BASE", "https://bevigrow-backend-dkay.onrender.com"
            ).rstrip("/")
            resp = requests.post(
                f"{base}/api/auth/login",
                json={"email": email, "password": password},
                timeout=60,
            )
            if resp.status_code == 200:
                user = resp.json().get("user", {})
                console.print(
                    f"  [green]BeviGrow tracker: signed in as "
                    f"{user.get('name') or user.get('email')}[/green]"
                )
            elif resp.status_code in (400, 401, 403):
                console.print("  [red]BeviGrow tracker: email or password rejected.[/red]")
            else:
                console.print(f"  [yellow]BeviGrow tracker: HTTP {resp.status_code}[/yellow]")
        except Exception as exc:
            console.print(f"  [yellow]BeviGrow tracker: could not reach it ({exc}).[/yellow]")
    else:
        console.print("  [yellow]BeviGrow tracker: not configured.[/yellow]")

    # --- Claude ---
    key = config_mod._str("ANTHROPIC_API_KEY")
    if key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=key, timeout=60.0, max_retries=1)
            client.messages.create(
                model=config_mod._str("ANTHROPIC_MODEL", "claude-opus-5"),
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            )
            console.print("  [green]Claude API key: working[/green]")
        except Exception as exc:
            console.print(f"  [red]Claude API key: {str(exc)[:160]}[/red]")
    else:
        console.print(
            "  [yellow]Claude API key: not set - research will use keyword rules only.[/yellow]"
        )

    # --- search ---
    tavily = config_mod._str("TAVILY_API_KEY")
    if tavily:
        try:
            import requests

            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": tavily, "query": "green coffee importer", "max_results": 1},
                timeout=45,
            )
            ok = resp.status_code == 200 and resp.json().get("results")
            console.print(
                "  [green]Tavily search: working[/green]" if ok
                else f"  [red]Tavily search: HTTP {resp.status_code}[/red]"
            )
        except Exception as exc:
            console.print(f"  [yellow]Tavily search: {str(exc)[:120]}[/yellow]")

    # --- gmail ---
    creds = Path(config_mod._str("GMAIL_CREDENTIALS_FILE", "config/gmail_credentials.json"))
    if not creds.is_absolute():
        creds = ROOT / creds
    if creds.exists():
        console.print("  [green]Gmail OAuth client file: found[/green]")
    else:
        console.print(
            f"  [yellow]Gmail OAuth client file: not yet at {creds} - "
            "see section 2 of README.md[/yellow]"
        )
