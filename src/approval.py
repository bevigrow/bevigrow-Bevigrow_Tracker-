"""
Human approval - the gate every message must pass.

Shows you, for each company:
    the research, the chosen contact, the chosen email address, and the exact
    final message

then asks:  APPROVE / EDIT / SKIP

Only APPROVE lets anything be sent. EDIT opens the message in Notepad (or your
$EDITOR) so you can change the wording, and the edited version is what gets
sent AND what gets stored in the tracker.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.config import settings
from src.logging_setup import console
from src.models import Channel, PreparedMessage, Priority, ResearchResult
from src.utils import truncate

_PRIORITY_COLOUR = {
    Priority.HIGH: "bold green",
    Priority.MEDIUM: "yellow",
    Priority.LOW: "dim yellow",
    Priority.IRRELEVANT: "red",
    Priority.UNCERTAIN: "magenta",
}


# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------
def show_research(result: ResearchResult) -> None:
    console.print()
    console.rule(f"[bold]{result.resolved_company_name}", style="cyan")

    facts = Table(show_header=False, box=None, padding=(0, 1))
    facts.add_column(style="dim", width=18)
    facts.add_column(overflow="fold")

    facts.add_row("Website", result.website or "[red]not found[/red]")
    facts.add_row("Country / city", ", ".join(p for p in (result.country, result.city) if p) or "-")
    facts.add_row("What they do", truncate(result.description, 220) or "-")
    facts.add_row("LinkedIn (company)", result.linkedin_company_url or "-")
    facts.add_row("Contact page", result.contact_page_url or "-")
    facts.add_row("Contact form", result.contact_form_url or "-")
    facts.add_row("Pages read", str(len(result.pages_crawled)))

    colour = _PRIORITY_COLOUR.get(result.relevance.priority, "white")
    facts.add_row(
        "Relevance",
        f"[{colour}]{result.relevance.priority.value}[/{colour}] - {truncate(result.relevance.reason, 260)}",
    )
    console.print(Panel(facts, title="Research", border_style="cyan"))

    # --- emails ---
    if result.emails:
        table = Table(title="Email addresses found", header_style="bold")
        table.add_column("Address", overflow="fold")
        table.add_column("Department")
        table.add_column("Score", justify="right")
        table.add_column("Mail server")
        table.add_column("Seen on", overflow="fold", max_width=42)
        for candidate in result.emails[:8]:
            mx = {True: "ok", False: "[red]NONE[/red]", None: "not checked"}[candidate.mx_ok]
            style = "green" if candidate.score >= 70 else ("red" if candidate.category == "avoid" else "")
            table.add_row(
                candidate.address, candidate.category, str(candidate.score), mx,
                truncate(candidate.source_url, 40), style=style,
            )
        console.print(table)
    else:
        console.print("[red]No email addresses were found on their website.[/red]")

    # --- people ---
    if result.people:
        table = Table(title="People found", header_style="bold")
        table.add_column("Name")
        table.add_column("Job title", overflow="fold")
        table.add_column("Score", justify="right")
        table.add_column("Source", overflow="fold", max_width=40)
        for person in result.people[:6]:
            table.add_row(person.name, person.title or "-", str(person.score),
                          truncate(person.source_url, 38))
        console.print(table)
    else:
        console.print("[yellow]No contact person could be verified publicly.[/yellow]")

    if result.warnings:
        console.print(
            Panel(
                "\n".join(f"- {w}" for w in result.warnings[:8]),
                title="Warnings", border_style="yellow",
            )
        )


def show_message(message: PreparedMessage, title: str = "Message ready for your approval") -> None:
    header = Table(show_header=False, box=None, padding=(0, 1))
    header.add_column(style="dim", width=10)
    header.add_column(overflow="fold")

    if message.channel is Channel.EMAIL:
        header.add_row("From", settings.gmail_sender or "[red]GMAIL_SENDER not set[/red]")
        header.add_row("To", ", ".join(message.to) or "[red]nobody[/red]")
        if message.cc:
            header.add_row("Cc", ", ".join(message.cc))
        if message.bcc:
            header.add_row("Bcc", ", ".join(message.bcc))
    else:
        header.add_row("Channel", message.channel.value)
        header.add_row("Where", message.target_url or "-")
    header.add_row("Subject", message.subject or "[red]empty[/red]")

    console.print(Panel(header, title=title, border_style="green"))
    console.print(Panel(Text(message.body), border_style="green", title="Body"))

    if message.personalisation_notes:
        console.print(
            "[dim]" + " | ".join(message.personalisation_notes[:4]) + "[/dim]"
        )


def show_mode_banner() -> None:
    if settings.test_mode:
        text = "TEST MODE - nothing will be sent. Messages are written to data/outbox/."
        style = "bold black on yellow"
    elif not settings.allow_real_sending:
        text = "LIVE MODE but ALLOW_REAL_SENDING=false - still nothing will be sent."
        style = "bold black on yellow"
    else:
        text = "REAL SENDING IS ENABLED - approved messages will actually go out."
        style = "bold white on red"
    console.print(Panel(text, style=style, expand=False))


# --------------------------------------------------------------------------
# Editing
# --------------------------------------------------------------------------
def _open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    try:
        if editor:
            subprocess.run([editor, str(path)], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["notepad.exe", str(path)], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-W", "-t", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:
        console.print(f"[red]Could not open an editor ({exc}).[/red]")
        console.print(f"Edit this file yourself, save it, then come back: {path}")


def edit_message(message: PreparedMessage) -> PreparedMessage:
    """Open the message in an editor and read back whatever you saved."""
    fd, name = tempfile.mkstemp(suffix=".txt", prefix="bevigrow-edit-", text=True)
    os.close(fd)
    path = Path(name)

    contents = (
        "# Edit the message below, SAVE the file, then CLOSE the editor.\n"
        "# Lines starting with # are ignored.\n"
        "# Keep the TO:/CC:/SUBJECT: lines and the --- separator.\n"
        "#\n"
        f"TO: {', '.join(message.to)}\n"
        f"CC: {', '.join(message.cc)}\n"
        f"SUBJECT: {message.subject}\n"
        "---\n"
        f"{message.body}"
    )
    path.write_text(contents, encoding="utf-8")

    _open_editor(path)
    Prompt.ask("[cyan]Press Enter once you have saved and closed the editor[/cyan]", default="")

    try:
        edited = path.read_text(encoding="utf-8")
    except Exception as exc:
        console.print(f"[red]Could not read your edits ({exc}). Keeping the original.[/red]")
        return message
    finally:
        try:
            path.unlink()
        except OSError:
            pass

    lines = [ln for ln in edited.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)

    head, sep, body = text.partition("\n---")
    if not sep:
        console.print("[red]The '---' separator was removed - keeping the original message.[/red]")
        return message

    def _header(field: str) -> str:
        match = re.search(rf"^{field}:\s*(.*)$", head, re.M | re.I)
        return match.group(1).strip() if match else ""

    to = [a.strip() for a in _header("TO").split(",") if a.strip()]
    cc = [a.strip() for a in _header("CC").split(",") if a.strip()]
    subject = _header("SUBJECT")

    message.to = to or message.to
    message.cc = cc
    message.subject = subject or message.subject
    message.body = body.strip("\n") + "\n"
    message.personalisation_notes.append("Message was edited by hand before sending.")
    return message


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------
def ask(message: PreparedMessage, extra_warning: str = "") -> tuple[str, PreparedMessage]:
    """
    Returns ("approve" | "skip" | "quit", possibly-edited message).

    Loops on EDIT so you can revise as many times as you like.
    """
    while True:
        show_message(message)
        if extra_warning:
            console.print(Panel(extra_warning, border_style="yellow", title="Please check"))

        if settings.test_mode:
            action_hint = "[green]a[/green]pprove (simulated send)"
        elif settings.allow_real_sending:
            action_hint = "[red]a[/red]pprove (THIS WILL REALLY SEND)"
        else:
            action_hint = "[green]a[/green]pprove (still simulated - ALLOW_REAL_SENDING=false)"

        choice = Prompt.ask(
            f"\n{action_hint} / [yellow]e[/yellow]dit / [cyan]s[/cyan]kip / [magenta]q[/magenta]uit",
            choices=["a", "e", "s", "q"],
            default="s",
        )

        if choice == "a":
            return "approve", message
        if choice == "s":
            return "skip", message
        if choice == "q":
            return "quit", message
        message = edit_message(message)
        extra_warning = ""


def confirm(question: str, default: bool = False) -> bool:
    answer = Prompt.ask(f"{question} [y/n]", choices=["y", "n"], default="y" if default else "n")
    return answer == "y"
