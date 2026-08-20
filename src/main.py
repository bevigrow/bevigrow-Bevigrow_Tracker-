"""
BeviGrow outreach - command line.

Everything you will ever type starts with:

    python -m src.main <command>

Run  `python -m src.main --help`  to see the list.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from src.config import DATA_DIR, RESULTS_DIR, ROOT, settings
from src.logging_setup import console, get_logger, setup_logging
from src.models import CompanyInput, Outcome
from src.utils import read_json

log = get_logger("main")

DEFAULT_INPUT = DATA_DIR / "companies.csv"


# ==========================================================================
# setup
# ==========================================================================
def cmd_setup(args) -> int:
    from src.setup_wizard import run

    return run()


# ==========================================================================
# check
# ==========================================================================
def cmd_check(args) -> int:
    from src import email_generator, llm, search as search_mod

    console.rule("[bold]BeviGrow outreach - configuration check")
    table = Table(show_header=True, header_style="bold")
    table.add_column("What")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")

    def row(name: str, ok: bool | None, detail: str) -> None:
        mark = {True: "[green]OK[/green]", False: "[red]MISSING[/red]", None: "[yellow]OPTIONAL[/yellow]"}[ok]
        table.add_row(name, mark, detail)

    env_file = ROOT / ".env"
    row(".env file", env_file.exists(),
        str(env_file) if env_file.exists() else "Copy .env.example to .env and fill it in.")

    row("Sender identity", bool(settings.sender_name),
        f"{settings.sender_name or '-'} / {settings.sender_title or 'no title'}"
        if settings.sender_name else "Set SENDER_NAME (and SENDER_TITLE) in .env")

    # --- templates ---
    problems = email_generator.check_templates()
    row("Message templates", not problems,
        "config/email_template.md and friends" if not problems else "; ".join(problems))

    # --- company list ---
    input_path = Path(args.input) if args.input else DEFAULT_INPUT
    if input_path.exists():
        try:
            from src.input_loader import load_companies

            count = len(load_companies(input_path))
            row("Company list", True, f"{input_path.name} - {count} companies")
        except Exception as exc:
            row("Company list", False, f"{input_path.name} could not be read: {exc}")
    else:
        row("Company list", False, f"Create {input_path}")

    # --- tracker ---
    if settings.tracker_configured:
        try:
            from src.tracker import get_client

            client = get_client()
            health = client.health()
            user = client.login()
            stats = client.stats()
            row("BeviGrow tracker", True,
                f"{settings.bevigrow_api_base} | db {health.get('database')} | "
                f"signed in as {user.get('name') or user.get('email')} | "
                f"{stats.get('total', '?')} records")
        except Exception as exc:
            row("BeviGrow tracker", False, str(exc)[:220])
    else:
        row("BeviGrow tracker", False,
            "Set BEVIGROW_EMAIL and BEVIGROW_PASSWORD in .env "
            "(your login for bevigrow-frontend-dkay.onrender.com)")

    # --- gmail ---
    if not settings.gmail_sender:
        row("Gmail sending", False, "Set GMAIL_SENDER in .env")
    elif not settings.gmail_credentials_file.exists():
        row("Gmail sending", False,
            f"Download the OAuth client JSON to {settings.gmail_credentials_file}")
    elif not settings.gmail_token_file.exists():
        row("Gmail sending", False, "Run: python -m src.main auth-gmail")
    else:
        try:
            from src.email_sender import gmail_service

            profile = gmail_service().users().getProfile(userId="me").execute()
            row("Gmail sending", True, f"connected as {profile.get('emailAddress')}")
        except Exception as exc:
            row("Gmail sending", False, str(exc)[:220])

    # --- claude ---
    if llm.available():
        row("Claude (research)", True, f"model {settings.anthropic_model}")
    else:
        row("Claude (research)", None,
            f"not in use - {llm.unavailable_reason()}. Research quality will be much lower.")

    # --- search ---
    provider = search_mod.available_provider()
    row("Web search", None if provider == "duckduckgo" else True,
        f"{provider}" + (" (no API key - free fallback, less reliable)"
                         if provider == "duckduckgo" else ""))

    console.print(table)

    # --- safety ---
    if settings.test_mode:
        mode = "[bold green]TEST MODE[/bold green] - nothing can be sent. This is the safe default."
    elif not settings.allow_real_sending:
        mode = "[bold yellow]TEST_MODE=false but ALLOW_REAL_SENDING=false[/bold yellow] - still nothing can be sent."
    else:
        mode = "[bold red]REAL SENDING IS ARMED[/bold red] - approved messages will actually go out."
    console.print(Panel(
        f"{mode}\n"
        f"Approval required : {settings.require_approval}\n"
        f"Max per run       : {settings.max_companies_per_run}\n"
        f"Daily send limit  : {settings.daily_send_limit}\n"
        f"Gap between sends : {settings.send_rate_limit_seconds}s\n"
        f"Follow-up after   : {settings.follow_up_days} days\n"
        f"Duplicate cooldown: {settings.duplicate_cooldown_days} days",
        title="Safety settings", border_style="cyan",
    ))
    return 0


# ==========================================================================
# auth-gmail
# ==========================================================================
def cmd_auth_gmail(args) -> int:
    from src.email_sender import SendError, authorise_interactively

    console.print(
        "A browser window will open. Sign in with the Google account you send outreach from, "
        "and approve the two permissions (send mail, read mail).\n"
        "Your password is never seen or stored by this program."
    )
    try:
        address = authorise_interactively()
    except SendError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    console.print(f"[green]Gmail is now connected: {address}[/green]")
    if not settings.gmail_sender:
        console.print(f"[yellow]Now set GMAIL_SENDER={address} in your .env file.[/yellow]")
    return 0


# ==========================================================================
# research / run
# ==========================================================================
def _companies_for(args) -> list[CompanyInput]:
    from src.input_loader import load_companies

    if args.company:
        return [
            CompanyInput(
                company=args.company,
                city=args.city or "",
                country=args.country or "",
                website=args.website or "",
            )
        ]

    path = Path(args.input) if args.input else DEFAULT_INPUT
    if not path.exists():
        console.print(f"[red]Company list not found: {path}[/red]")
        console.print("Create it, or pass --company \"Some Company Ltd\" for a single test.")
        return []
    return load_companies(path)


def cmd_research(args) -> int:
    from src import approval
    from src.research import research_company

    companies = _companies_for(args)
    if not companies:
        return 1

    limit = args.limit or len(companies)
    for company in companies[:limit]:
        result = research_company(company, use_llm=not args.no_llm)
        approval.show_research(result)
        console.print(f"[dim]Saved to data/results/research-*.json[/dim]")
    return 0


def cmd_run(args) -> int:
    from src import approval
    from src.pipeline import process_company

    companies = _companies_for(args)
    if not companies:
        return 1

    limit = args.limit if args.limit is not None else settings.max_companies_per_run
    batch = companies[:limit] if limit else companies

    approval.show_mode_banner()
    console.print(
        f"[bold]{len(batch)} company/companies queued[/bold] "
        f"(list has {len(companies)}; limit {limit or 'none'})\n"
    )

    if settings.can_send_for_real and not args.yes:
        if not approval.confirm(
            "REAL SENDING IS ENABLED. Continue?", default=False
        ):
            console.print("Stopped.")
            return 0

    results = []
    try:
        for i, company in enumerate(batch, start=1):
            console.print(f"\n[bold cyan]({i}/{len(batch)})[/bold cyan] {company.company}")
            try:
                outcome = process_company(
                    company,
                    interactive=not args.non_interactive,
                    use_llm=None if not args.no_llm else False,
                    skip_duplicate_check=args.ignore_duplicates,
                    research_only=False,
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]Run stopped.[/yellow]")
                break
            except Exception as exc:
                log.exception("Unhandled error for %s", company.company)
                from src.models import CompanyResult

                outcome = CompanyResult(
                    company=company.company, outcome=Outcome.FAILED,
                    reason=f"Unexpected error: {exc}", error=str(exc),
                )
            results.append(outcome)
    except KeyboardInterrupt:
        console.print("\n[yellow]Run stopped.[/yellow]")

    _print_summary(results)
    return 0


def _print_summary(results: list) -> None:
    if not results:
        return
    table = Table(title="Run summary", header_style="bold")
    table.add_column("Company", overflow="fold")
    table.add_column("Result")
    table.add_column("Reason", overflow="fold")
    table.add_column("Tracker", justify="right")

    colours = {
        Outcome.SUCCESS: "green",
        Outcome.SIMULATED: "cyan",
        Outcome.ALREADY_CONTACTED: "yellow",
        Outcome.NEEDS_REVIEW: "yellow",
        Outcome.NO_EMAIL: "yellow",
        Outcome.FORM_REQUIRED: "yellow",
        Outcome.LINKEDIN_MANUAL: "yellow",
        Outcome.IRRELEVANT: "red",
        Outcome.FAILED: "red",
        Outcome.SKIPPED: "dim",
    }
    for r in results:
        table.add_row(
            r.company,
            f"[{colours.get(r.outcome, 'white')}]{r.outcome.value}[/]",
            (r.reason or "")[:160],
            str(r.tracker_record_id or "-"),
        )
    console.print(table)
    console.print(f"[dim]Full details in {RESULTS_DIR}[/dim]")


# ==========================================================================
# tracker / followups / replies / linkedin
# ==========================================================================
def cmd_tracker(args) -> int:
    from src.tracker import get_client

    client = get_client()
    if args.list:
        records = client.list_outreach(search=args.search, status=args.status, limit=args.limit or 50)
        table = Table(title=f"{len(records)} outreach records", header_style="bold")
        for col in ("ID", "Company", "Channel", "Email", "Contacted", "Status", "Next follow-up"):
            table.add_column(col, overflow="fold")
        for r in records:
            table.add_row(
                str(r.get("id")), r.get("company_name", ""), r.get("contact_method", ""),
                r.get("email") or "-", r.get("contacted_on") or "-",
                r.get("status", ""), r.get("next_follow_up") or "-",
            )
        console.print(table)
        return 0

    stats = client.stats()
    table = Table(title="BeviGrow outreach statistics", header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in stats.items():
        if isinstance(value, (int, float, str)):
            table.add_row(str(key).replace("_", " "), str(value))
    console.print(table)
    return 0


def cmd_followups(args) -> int:
    from src import followups

    if args.send:
        followups.process(interactive=not args.non_interactive, limit=args.limit)
        return 0

    due = followups.due_records()
    followups.show_due(due)
    soon = followups.upcoming(days_ahead=args.upcoming)
    if soon:
        table = Table(title=f"Coming up in the next {args.upcoming} days", header_style="bold")
        for col in ("ID", "Company", "Due", "Status"):
            table.add_column(col)
        for r in soon:
            table.add_row(str(r.get("id")), r.get("company_name", ""),
                          r.get("next_follow_up") or "-", r.get("status", ""))
        console.print(table)
    if due:
        console.print("\nTo prepare and send them: [bold]python -m src.main followups --send[/bold]")
    return 0


def cmd_replies(args) -> int:
    from src import replies

    replies.process(days=args.days, interactive=not args.non_interactive)
    return 0


def cmd_linkedin(args) -> int:
    from src import linkedin

    tasks = linkedin.list_tasks(status=None if args.all else "pending")
    if not tasks:
        console.print("[green]No LinkedIn tasks waiting.[/green]")
        return 0

    table = Table(title=f"{len(tasks)} LinkedIn tasks", header_style="bold")
    for col in ("Company", "Person", "URL", "Prepared", "Status"):
        table.add_column(col, overflow="fold")
    for t in tasks:
        table.add_row(t.get("company", ""), t.get("person") or "-",
                      t.get("linkedin_url") or "-", t.get("prepared_on", ""), t.get("status", ""))
    console.print(table)
    console.print(f"\nFull text with the messages to copy: [bold]{linkedin.TASKS_MARKDOWN}[/bold]")
    console.print('After sending one: [bold]python -m src.main linkedin-done "Company Name"[/bold]')
    return 0


def cmd_linkedin_done(args) -> int:
    from src import linkedin
    from src.followups import research_from_record
    from src.models import TrackerStatus
    from src.tracker import build_notes, build_outreach_payload, get_client
    from src.utils import days_from_now
    from datetime import date

    tasks = [t for t in linkedin.list_tasks("pending")
             if t.get("company", "").lower() == args.company.lower()]
    if not tasks:
        console.print(f"[red]No pending LinkedIn task found for '{args.company}'.[/red]")
        return 1
    task = tasks[0]

    message = linkedin.build_tracker_message(task)
    fake_record = {
        "company_name": task["company"],
        "country": task.get("country", ""),
        "website": task.get("website", ""),
        "contact_person": task.get("person", ""),
    }
    research = research_from_record(fake_record)

    tracker_id = None
    if settings.tracker_configured:
        payload = build_outreach_payload(
            result=research,
            message=message,
            contact_person=task.get("person", ""),
            status=TrackerStatus.WAITING_REPLY,
            contacted_on=date.today().isoformat(),
            next_action=f"Follow up on LinkedIn if no reply by {days_from_now(settings.follow_up_days)}",
            next_follow_up=days_from_now(settings.follow_up_days),
            notes=f"Contacted on LinkedIn: {task.get('linkedin_url', '')}. "
                  f"{'Person: ' + task['person'] + '. ' if task.get('person') else ''}"
                  f"Prepared {task.get('prepared_on', '')}.",
        )
        try:
            record = get_client().create_outreach(payload)
            tracker_id = record.get("id")
            console.print(f"[green]Logged in the tracker as record #{tracker_id}.[/green]")
        except Exception as exc:
            console.print(f"[red]Tracker write failed: {exc}[/red]")
    else:
        console.print("[yellow]Tracker not configured - the task was marked done locally only.[/yellow]")

    linkedin.mark_done(task["company"], tracker_id)

    from src.duplicate_checker import record_locally
    from src.utils import sha256

    record_locally(
        company=task["company"], website=task.get("website", ""), email="",
        channel="linkedin", tracker_id=tracker_id,
        message_hash=sha256(message.body), simulated=False,
    )
    console.print(f"[green]LinkedIn outreach to {task['company']} recorded.[/green]")
    return 0


def cmd_report(args) -> int:
    files = sorted(RESULTS_DIR.glob("result-*.json"))
    if not files:
        console.print("No results yet. Run: python -m src.main run --limit 1")
        return 0

    table = Table(title=f"{len(files)} processed companies", header_style="bold")
    for col in ("Company", "Result", "When", "Tracker", "Reason"):
        table.add_column(col, overflow="fold")
    counts: dict[str, int] = {}
    for path in files:
        data = read_json(path, default={}) or {}
        outcome = data.get("outcome", "?")
        counts[outcome] = counts.get(outcome, 0) + 1
        table.add_row(
            data.get("company", path.stem), outcome, (data.get("timestamp") or "")[:19],
            str(data.get("tracker_record_id") or "-"), (data.get("reason") or "")[:120],
        )
    console.print(table)
    console.print("  ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return 0


# ==========================================================================
# argument parsing
# ==========================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="BeviGrow AI outreach automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
typical first run:
  python -m src.main check
  python -m src.main research --company "Benecke Coffee GmbH & Co. KG" --country Germany
  python -m src.main run --limit 1
""",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="answer a few questions and write your .env for you")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("check", help="verify configuration and connections")
    p.add_argument("--input", help="company list to verify")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("auth-gmail", help="one-time Gmail authorisation (opens a browser)")
    p.set_defaults(func=cmd_auth_gmail)

    def add_selection(sp):
        sp.add_argument("--input", help=f"company list file (default {DEFAULT_INPUT})")
        sp.add_argument("--company", help="research one company by name instead of a file")
        sp.add_argument("--city", help="city, used with --company")
        sp.add_argument("--country", help="country, used with --company")
        sp.add_argument("--website", help="known website, used with --company")
        sp.add_argument("--limit", type=int, help="how many companies to process")
        sp.add_argument("--no-llm", action="store_true", help="do not use Claude")

    p = sub.add_parser("research", help="research only - never prepares or sends anything")
    add_selection(p)
    p.set_defaults(func=cmd_research)

    p = sub.add_parser("run", help="the full pipeline, with approval before every send")
    add_selection(p)
    p.add_argument("--non-interactive", action="store_true",
                   help="no prompts (only useful for research/dry checks)")
    p.add_argument("--ignore-duplicates", action="store_true",
                   help="skip the already-contacted check (use with care)")
    p.add_argument("--yes", action="store_true", help="skip the 'real sending' confirmation")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("tracker", help="BeviGrow tracker statistics or records")
    p.add_argument("--list", action="store_true", help="list records instead of statistics")
    p.add_argument("--search", help="filter by company, person, website or notes")
    p.add_argument("--status", help="filter by status, e.g. waiting_reply")
    p.add_argument("--limit", type=int, help="how many records to show")
    p.set_defaults(func=cmd_tracker)

    p = sub.add_parser("followups", help="what is due, and send follow-ups with approval")
    p.add_argument("--send", action="store_true", help="actually prepare and send them")
    p.add_argument("--limit", type=int, help="how many to handle")
    p.add_argument("--upcoming", type=int, default=14, help="days ahead to preview")
    p.add_argument("--non-interactive", action="store_true")
    p.set_defaults(func=cmd_followups)

    p = sub.add_parser("replies", help="read Gmail replies and update the tracker")
    p.add_argument("--days", type=int, default=30, help="how far back to look")
    p.add_argument("--non-interactive", action="store_true")
    p.set_defaults(func=cmd_replies)

    p = sub.add_parser("linkedin", help="the manual LinkedIn task list")
    p.add_argument("--all", action="store_true", help="include completed tasks")
    p.set_defaults(func=cmd_linkedin)

    p = sub.add_parser("linkedin-done", help="record that you sent a LinkedIn message")
    p.add_argument("company", help="company name exactly as shown in the task list")
    p.set_defaults(func=cmd_linkedin_done)

    p = sub.add_parser("report", help="summary of everything processed so far")
    p.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(verbose=args.verbose)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
        return 130
    except Exception as exc:
        log.exception("Command failed")
        console.print(f"[red]Error: {exc}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
