"""
The pipeline - what happens to ONE company, start to finish.

    duplicate check -> research -> relevance -> pick channel -> build message
    -> YOUR APPROVAL -> send (or simulate) -> BeviGrow tracker -> local log

Every branch ends in a CompanyResult with an explicit outcome and a reason, so
nothing ever fails silently.
"""

from __future__ import annotations

from datetime import date

from src.config import RESULTS_DIR, settings
from src.logging_setup import console, get_logger
from src.models import (
    Channel,
    CompanyInput,
    CompanyResult,
    Outcome,
    PreparedMessage,
    Priority,
    ResearchResult,
    TrackerStatus,
)
from src.utils import days_from_now, now_iso, slugify, write_json
from src import (
    approval,
    duplicate_checker,
    email_finder,
    email_generator,
    email_sender,
    linkedin,
    relevance,
    research as research_mod,
    tracker as tracker_mod,
    website_forms,
)

log = get_logger("pipeline")


def _finish(result: CompanyResult) -> CompanyResult:
    result.timestamp = now_iso()
    path = RESULTS_DIR / f"result-{slugify(result.company)}.json"
    write_json(path, result.to_dict())
    return result


def _log_to_tracker(
    outcome: CompanyResult,
    research: ResearchResult,
    message: PreparedMessage,
    contact_person: str,
    status: TrackerStatus,
    next_action: str,
    notes: str,
    contacted_on: str | None = None,
    next_follow_up: str | None = None,
) -> None:
    """Write the outreach into the BeviGrow tracker. Failures are recorded, not fatal."""
    if not settings.tracker_configured:
        outcome.reason += " (Tracker not configured - record NOT saved to BeviGrow.)"
        log.warning("Tracker credentials missing - skipping the tracker write.")
        return

    payload = tracker_mod.build_outreach_payload(
        result=research,
        message=message,
        contact_person=contact_person,
        status=status,
        contacted_on=contacted_on or date.today().isoformat(),
        next_action=next_action,
        next_follow_up=next_follow_up or days_from_now(settings.follow_up_days),
        notes=notes,
    )
    try:
        client = tracker_mod.get_client()
        try:
            payload["owner_id"] = client.user.get("id")
        except Exception:
            payload.pop("owner_id", None)
        record = client.create_outreach(payload)
        outcome.tracker_record_id = record.get("id")
        outcome.next_follow_up = record.get("next_follow_up") or payload.get("next_follow_up", "")
        console.print(f"[green]Logged in BeviGrow tracker as record #{record.get('id')}[/green]")
    except Exception as exc:
        log.error("Could not write to the BeviGrow tracker: %s", exc)
        outcome.error = f"Tracker write failed: {exc}"
        outcome.reason += " (Tracker write FAILED - add this one by hand.)"


# --------------------------------------------------------------------------
def process_company(
    company: CompanyInput,
    *,
    interactive: bool = True,
    use_llm: bool | None = None,
    skip_duplicate_check: bool = False,
    research_only: bool = False,
) -> CompanyResult:
    """Run one company through the whole pipeline."""
    outcome = CompanyResult(company=company.company)

    # --- 1. cheap duplicate check before spending research effort ----------
    if not skip_duplicate_check:
        verdict = duplicate_checker.check(company.company, company.website)
        if verdict.is_duplicate:
            console.print(
                f"[yellow]Already contacted - review existing record.[/yellow] {verdict.summary}"
            )
            outcome.outcome = Outcome.ALREADY_CONTACTED
            outcome.reason = verdict.summary
            outcome.tracker_record_id = verdict.record_id
            return _finish(outcome)

    # --- 2. research -------------------------------------------------------
    research = research_mod.research_company(company, use_llm=use_llm)
    outcome.research = research

    if interactive:
        approval.show_research(research)

    if research_only:
        outcome.outcome = Outcome.SUCCESS
        outcome.reason = "Research only - no message prepared."
        return _finish(outcome)

    # --- 3. duplicate check again, now that we know the website/email ------
    if not skip_duplicate_check:
        verdict = duplicate_checker.check_research(research)
        if verdict.is_duplicate:
            console.print(
                f"[yellow]Already contacted - review existing record.[/yellow] {verdict.summary}"
            )
            outcome.outcome = Outcome.ALREADY_CONTACTED
            outcome.reason = verdict.summary
            outcome.tracker_record_id = verdict.record_id
            return _finish(outcome)

    # --- 4. relevance gate -------------------------------------------------
    proceed, why_not = relevance.should_contact(research.relevance)
    if not proceed:
        outcome.outcome = Outcome.IRRELEVANT
        outcome.reason = why_not
        console.print(f"[red]Skipping: {why_not}[/red]")
        return _finish(outcome)

    person = research_mod.best_person(research)
    contact_person = person.name if person else ""

    # --- 5. choose the channel --------------------------------------------
    to, cc, email_reasoning, needs_review = email_finder.select_recipients(research.emails)
    email_notes = email_finder.notes_for_tracker(research.emails)

    linkedin_url, linkedin_note = linkedin.pick_target(research, person)
    if linkedin_url and research.relevance.priority in (Priority.HIGH, Priority.MEDIUM):
        why = "high-priority prospect" if to else "no usable email address"
        # If the task points at the company page rather than this person's own
        # profile, the message must address the company, not them by name.
        li_person = person if "/in/" in linkedin_url else None
        _queue_linkedin(research, li_person, linkedin_url, f"{why} ({linkedin_note})")

    if to:
        return _do_email(outcome, research, person, contact_person, to, cc,
                         email_reasoning, email_notes, needs_review, interactive)

    if research.contact_form_url or research.contact_page_url:
        return _do_website_form(outcome, research, person, contact_person,
                                email_notes, interactive)

    if linkedin_url:
        outcome.outcome = Outcome.LINKEDIN_MANUAL
        outcome.reason = (
            "No email address and no contact form found. A LinkedIn task has been prepared "
            "for you in data/results/linkedin_tasks.md."
        )
        console.print(f"[yellow]{outcome.reason}[/yellow]")
        return _finish(outcome)

    outcome.outcome = Outcome.NO_EMAIL
    outcome.reason = (
        "No email address, no contact form and no LinkedIn page could be found. "
        "This company needs manual research."
    )
    console.print(f"[red]{outcome.reason}[/red]")
    return _finish(outcome)


# --------------------------------------------------------------------------
def _queue_linkedin(research: ResearchResult, person, linkedin_url: str, why: str) -> None:
    try:
        message = email_generator.build_linkedin(research, person, linkedin_url)
        linkedin.add_task(research, person, message, why=why)
    except Exception as exc:
        log.warning("Could not prepare the LinkedIn task: %s", exc)


def _do_email(outcome, research, person, contact_person, to, cc,
              email_reasoning, email_notes, needs_review, interactive) -> CompanyResult:
    try:
        message = email_generator.build_email(research, person, to, cc)
    except Exception as exc:
        outcome.outcome = Outcome.FAILED
        outcome.reason = f"Could not build the email: {exc}"
        outcome.error = str(exc)
        return _finish(outcome)

    outcome.message = message

    problems = email_sender.validate_message(message)
    warning_lines: list[str] = []
    if needs_review:
        warning_lines.append(email_reasoning)
    if problems:
        warning_lines.append("Problems: " + "; ".join(problems))
    if research.relevance.priority in (Priority.UNCERTAIN, Priority.LOW):
        warning_lines.append(
            f"Relevance is {research.relevance.priority.value}: {research.relevance.reason}"
        )

    if problems:
        outcome.outcome = Outcome.NEEDS_REVIEW
        outcome.reason = "; ".join(problems)
        console.print(f"[red]Cannot send: {outcome.reason}[/red]")
        if interactive:
            approval.show_message(message, "This message is NOT sendable as it stands")
        return _finish(outcome)

    # --- approval ---------------------------------------------------------
    if interactive and settings.require_approval:
        decision, message = approval.ask(message, "\n".join(warning_lines))
        outcome.message = message
        if decision == "skip":
            outcome.outcome = Outcome.SKIPPED
            outcome.reason = "You skipped this company."
            return _finish(outcome)
        if decision == "quit":
            outcome.outcome = Outcome.SKIPPED
            outcome.reason = "Run stopped by you."
            raise KeyboardInterrupt
    elif settings.require_approval:
        outcome.outcome = Outcome.NEEDS_REVIEW
        outcome.reason = "Approval is required but this run is not interactive."
        return _finish(outcome)

    # --- send -------------------------------------------------------------
    send_result = email_sender.send(message, research.resolved_company_name)
    if not send_result.ok:
        outcome.outcome = Outcome.FAILED
        outcome.reason = f"Sending failed: {send_result.error}"
        outcome.error = send_result.error
        console.print(f"[red]{outcome.reason}[/red]")
        return _finish(outcome)

    outcome.sent_at = now_iso()
    outcome.outcome = Outcome.SIMULATED if send_result.simulated else Outcome.SUCCESS
    outcome.reason = (
        f"Simulated - written to {send_result.outbox_file}"
        if send_result.simulated
        else f"Email sent to {', '.join(message.to)}"
    )

    # --- tracker ----------------------------------------------------------
    notes = tracker_mod.build_notes(
        research, email_notes,
        extra=(["Sent in TEST MODE (simulated)."] if send_result.simulated else None),
    )
    _log_to_tracker(
        outcome, research, message,
        contact_person=contact_person,
        status=TrackerStatus.WAITING_REPLY,
        next_action=f"Follow up if no reply by {days_from_now(settings.follow_up_days)}",
        notes=notes,
    )

    duplicate_checker.record_locally(
        company=research.resolved_company_name,
        website=research.website,
        email=message.to[0] if message.to else "",
        channel=Channel.EMAIL.value,
        tracker_id=outcome.tracker_record_id,
        message_hash=email_sender.message_fingerprint(message),
        simulated=send_result.simulated,
    )
    return _finish(outcome)


def _do_website_form(outcome, research, person, contact_person,
                     email_notes, interactive) -> CompanyResult:
    form_url = research.contact_form_url or research.contact_page_url
    try:
        message = email_generator.build_website_enquiry(research, person, form_url)
    except Exception as exc:
        outcome.outcome = Outcome.FAILED
        outcome.reason = f"Could not build the website enquiry: {exc}"
        return _finish(outcome)

    outcome.message = message
    console.print(
        f"[yellow]No suitable email address found. Using their contact form:[/yellow] {form_url}"
    )

    if interactive and settings.require_approval:
        decision, message = approval.ask(
            message, "This will be typed into the company's own website contact form."
        )
        outcome.message = message
        if decision == "skip":
            outcome.outcome = Outcome.SKIPPED
            outcome.reason = "You skipped this company."
            return _finish(outcome)
        if decision == "quit":
            raise KeyboardInterrupt
    elif settings.require_approval:
        outcome.outcome = Outcome.FORM_REQUIRED
        outcome.reason = "A contact form is needed but this run is not interactive."
        return _finish(outcome)

    form_result = website_forms.prepare_and_submit(
        form_url, message, research.resolved_company_name, submit=True
    )

    if form_result.captcha_detected:
        outcome.outcome = Outcome.FORM_REQUIRED
        outcome.reason = (
            f"The form at {form_url} is protected by a CAPTCHA. The completed message is "
            f"saved at {form_result.preview_file} - please submit it yourself."
        )
        console.print(f"[yellow]{outcome.reason}[/yellow]")
        return _finish(outcome)

    if not form_result.ok and not form_result.submitted:
        outcome.outcome = Outcome.FORM_REQUIRED
        outcome.reason = (
            f"Could not complete the form automatically ({form_result.error}). "
            f"The message is ready at {form_result.preview_file}."
        )
        console.print(f"[yellow]{outcome.reason}[/yellow]")
        return _finish(outcome)

    outcome.sent_at = now_iso()
    outcome.outcome = Outcome.SIMULATED if form_result.simulated else Outcome.SUCCESS
    outcome.reason = (
        f"Simulated form submission - preview at {form_result.preview_file}"
        if form_result.simulated
        else f"Enquiry submitted through {form_url}"
    )

    notes = tracker_mod.build_notes(
        research,
        email_notes or "No email address published - used their website contact form.",
        extra=(["Submitted in TEST MODE (simulated)."] if form_result.simulated else None),
    )
    message.target_url = form_url
    _log_to_tracker(
        outcome, research, message,
        contact_person=contact_person,
        status=TrackerStatus.WAITING_REPLY,
        next_action=f"Follow up if no reply by {days_from_now(settings.follow_up_days)}",
        notes=notes,
    )
    duplicate_checker.record_locally(
        company=research.resolved_company_name,
        website=research.website,
        email="",
        channel=Channel.WEBSITE_FORM.value,
        tracker_id=outcome.tracker_record_id,
        message_hash=email_sender.message_fingerprint(message),
        simulated=form_result.simulated,
    )
    return _finish(outcome)
