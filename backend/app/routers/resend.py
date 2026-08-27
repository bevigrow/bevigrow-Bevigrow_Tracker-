"""Resend Campaign endpoints: intentional resend to previously contacted recipients.

Integrates with the existing campaign sender pipeline. Creates campaigns that the
scheduler picks up and processes according to sending mode and daily limits.

Reuses New Campaign's template, placeholder, and sending components for full feature parity.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from io import StringIO, BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Outreach, Campaign, CampaignTarget, CampaignStatus, SendMode, TargetState, EmailTemplate, ContactMethod, OutreachStatus
from ..services import campaigns as cm
from ..services import templating, importer

log = logging.getLogger("bevigrow.resend")

router = APIRouter(prefix="/api/resend", tags=["resend"])


@router.get("/health")
def resend_health():
    """Health check for resend router."""
    print("[HEALTH] Resend router health check called", flush=True)
    return {"status": "ok", "router": "resend"}


@router.post("/review-simple")
def review_simple():
    """Simplest test endpoint — no dependencies."""
    print("[SIMPLE] Called", flush=True)
    return {"test": "ok", "message": "Simple endpoint works"}




@router.get("/templates")
def list_templates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Get available email templates for Resend Campaign (reuses New Campaign templates)."""
    stmt = select(EmailTemplate).order_by(EmailTemplate.created_at.desc())
    templates = db.scalars(stmt).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "subject": t.subject,
            "placeholders": list(set(
                m.group(1) or m.group(2) or m.group(3) or m.group(4) or m.group(5)
                for m in templating.PLACEHOLDER.finditer(f"{t.subject or ''}\n{t.body or ''}")
            )),
        }
        for t in templates
    ]


@router.post("/preview")
def preview_email(
    email: str = Form(...),
    company_name: str = Form(...),
    contact_person: str = Form(default=None),
    country: str = Form(default=None),
    category: str = Form(default=None),
    location: str = Form(default=None),
    template_id: int = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Preview filled email for a single recipient (placeholder substitution only)."""
    log.info(f"Previewing template {template_id} for {email}")

    # Get template
    template = db.get(EmailTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Create a mock target for preview with all mapped fields
    mock_target = CampaignTarget(
        id=0,
        campaign_id=0,
        position=0,
        email=email,
        company_name=company_name,
        contact_person=contact_person,
        country=country,
        location=location,
        category=category,
    )

    try:
        subject, unfilled_subject = templating.fill(template.subject or "", mock_target)
        body, unfilled_body = templating.fill(template.body or "", mock_target)

        unfilled = sorted(set(unfilled_subject + unfilled_body))

        return {
            "subject": subject,
            "body": body,
            "unfilled_placeholders": unfilled,
            "can_send": True,  # Allow sending even with missing placeholders
        }
    except Exception as e:
        log.error(f"Preview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


def parse_file(file: UploadFile) -> tuple[list[dict], dict]:
    """Parse CSV or XLSX file using importer's proven logic from New Campaign.

    Returns list of mapped rows with email, company_name, country, etc.
    """
    print(f"[PARSE] START: {file.filename}", flush=True)

    try:
        if not file or not file.filename:
            raise ValueError("No file provided")

        content = file.file.read()
        if not content:
            raise ValueError("File is empty")

        print(f"[PARSE] Calling importer.parse()", flush=True)
        # Use the PROVEN importer from New Campaign
        report = importer.parse(content, file.filename)

        print(f"[PARSE] Importer stats:", flush=True)
        print(f"  - Total rows from importer: {len(report.rows)}", flush=True)
        print(f"  - Total addresses found: {report.addresses}", flush=True)
        print(f"  - File rows: {report.file_rows}", flush=True)
        print(f"  - Without email: {report.without_email}", flush=True)
        print(f"  - Invalid emails: {report.invalid_emails}", flush=True)

        # Convert ParsedRow objects to dicts for our use
        # Include ONLY rows that have a valid email (skip_reason is None)
        mapped_rows = []
        skipped_count = 0
        for idx, parsed_row in enumerate(report.rows):
            if parsed_row.skip_reason:
                print(f"[PARSE] Row {idx}: SKIPPED - {parsed_row.skip_reason}", flush=True)
                skipped_count += 1
                continue

            if not parsed_row.email:
                print(f"[PARSE] Row {idx}: NO EMAIL but no skip_reason?!", flush=True)
                skipped_count += 1
                continue

            mapped = {
                'email': parsed_row.email,
                'company_name': parsed_row.company_name,
                'contact_person': parsed_row.contact_person,
                'country': parsed_row.country,
                'location': parsed_row.location,
                'category': parsed_row.category,
                'website': parsed_row.website,
                'phone': parsed_row.phone,
                'linkedin': parsed_row.linkedin,
                'contact_form': parsed_row.contact_form,
            }
            # Remove None values
            mapped = {k: v for k, v in mapped.items() if v is not None}
            mapped_rows.append(mapped)
            print(f"[PARSE] Row {idx}: OK - {parsed_row.email} / {parsed_row.company_name}", flush=True)

        print(f"[PARSE] Final: {len(mapped_rows)} with emails, {skipped_count} skipped", flush=True)
        log.info(f"Parsed {len(mapped_rows)} valid rows from {file.filename} (skipped {skipped_count})")
        return mapped_rows, {}

    except ValueError:
        raise
    except Exception as e:
        log.error(f"File parsing error: {e}", exc_info=True)
        print(f"[PARSE] ERROR: {type(e).__name__}: {e}", flush=True)
        raise ValueError(f"File parsing error: {str(e)}")


def extract_email_field(mapped_row: dict) -> str | None:
    """Extract email from row (importer already validated it)."""
    email = mapped_row.get('email')
    if email:
        return str(email).strip().lower()
    return None


def check_contact_history(db: Session, email: str) -> dict:
    """Check if email was previously contacted."""
    try:
        stmt = select(Outreach).where(Outreach.email == email.lower()).order_by(Outreach.contacted_on.desc())
        outreach = db.scalars(stmt).first()

        return {
            'email': email,
            'is_in_history': outreach is not None,
            'last_sent_date': str(outreach.contacted_on) if outreach and outreach.contacted_on else None,
        }
    except Exception as e:
        log.warning(f"Contact history check failed for {email}: {e}")
        return {'email': email, 'is_in_history': False, 'last_sent_date': None}


@router.post("/review")
def resend_review(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Analyze uploaded file and identify previously contacted recipients."""
    print(f"[REVIEW] START: file={file.filename if file else 'None'}", flush=True)

    try:
        if not file:
            print("[REVIEW] ERROR: file is None", flush=True)
            return JSONResponse(status_code=200, content={"error": "No file provided", "total_recipients": 0, "previously_contacted": 0, "recipients": []})

        if not file.filename:
            print("[REVIEW] ERROR: file.filename is empty", flush=True)
            return JSONResponse(status_code=200, content={"error": "File has no name", "total_recipients": 0, "previously_contacted": 0, "recipients": []})

        print(f"[REVIEW] Parsing file: {file.filename}", flush=True)
        result = _resend_review_impl(file, db)
        print(f"[REVIEW] SUCCESS: {len(result.get('recipients', []))} recipients", flush=True)
        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        print(f"[REVIEW] ERROR: {type(e).__name__}: {str(e)[:200]}", flush=True)
        import traceback
        traceback.print_exc()

        error_response = {
            "error": str(e)[:200],
            "total_recipients": 0,
            "previously_contacted": 0,
            "recipients": []
        }
        print(f"[REVIEW] RETURNING ERROR RESPONSE: {error_response}", flush=True)
        return JSONResponse(status_code=200, content=error_response)


def _resend_review_impl(file: UploadFile, db: Session):
    """Implementation of resend review logic - shows ALL recipients in file."""
    print(f"[IMPL] START: file={file.filename}", flush=True)
    log.info(f"[IMPL] 1. Started for file: {file.filename}")

    # Parse file
    try:
        print(f"[IMPL] Calling parse_file", flush=True)
        log.info(f"[IMPL] 2. Calling parse_file")
        rows, header_map = parse_file(file)
        print(f"[IMPL] Got {len(rows)} rows from parse_file", flush=True)
        log.info(f"[IMPL] 3. Parsed {len(rows)} rows from file")
    except ValueError as e:
        print(f"[IMPL] ValueError in parse_file: {e}", flush=True)
        log.warning(f"[IMPL] File parse error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[IMPL] Exception in parse_file: {type(e).__name__}: {e}", flush=True)
        log.error(f"[IMPL] Unexpected error in parse_file: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File parse error: {str(e)[:100]}")

    if not rows:
        print("[IMPL] No rows found after parsing", flush=True)
        log.info("[IMPL] 4. No rows found, returning empty")
        return {
            'total_recipients': 0,
            'previously_contacted': 0,
            'recipients': [],
        }

    print(f"[IMPL] Processing {len(rows)} rows", flush=True)
    log.info(f"[IMPL] 5. Processing {len(rows)} rows")
    recipients = []
    previously_contacted = 0

    # Process each row - resend campaign accepts ALL emails, tracks if previously contacted
    for idx, mapped_row in enumerate(rows):
        try:
            email = extract_email_field(mapped_row)
            if not email:
                log.debug(f"Row {idx}: No email field found")
                continue

            company = mapped_row.get('company_name') or 'Unknown'
            contact_person = mapped_row.get('contact_person')

            # Check if previously contacted (informational only, not a filter)
            history = check_contact_history(db, email)

            recipient = {
                'email': email,
                'company_name': str(company) if company else 'Unknown',
                'contact_person': str(contact_person) if contact_person else None,
                'country': mapped_row.get('country'),
                'location': mapped_row.get('location'),
                'category': mapped_row.get('category'),
                'is_in_history': history['is_in_history'],
                'last_sent_date': history['last_sent_date'],
            }
            recipients.append(recipient)

            if history['is_in_history']:
                previously_contacted += 1
        except Exception as row_error:
            print(f"[IMPL] Row {idx} error: {row_error}", flush=True)
            log.warning(f"Row {idx} processing error: {row_error}", exc_info=True)
            continue

    print(f"[IMPL] DONE: {len(recipients)} recipients, {previously_contacted} previously contacted", flush=True)
    log.info(f"Review complete: {len(recipients)} total, {previously_contacted} previously contacted")
    result = {
        'total_recipients': len(recipients),
        'previously_contacted': previously_contacted,
        'recipients': recipients,
    }
    print(f"[IMPL] RETURNING: {result}", flush=True)
    log.debug(f"Returning review result: {result}")
    return result


@router.post("/send")
def resend_send(
    file: UploadFile = File(...),
    campaign_name: str = Form(...),
    template_id: int = Form(...),
    sending_mode: str = Form(...),
    resend_reason: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Queue resend campaign with template for previously contacted recipients."""
    log.info(f"Queuing resend: campaign={campaign_name}, template={template_id}, mode={sending_mode}, user={user.email}")

    try:
        log.info("[SEND] 1. Starting resend_send_impl")
        result = _resend_send_impl(file, campaign_name, template_id, sending_mode, resend_reason, db, user)
        log.info(f"[SEND] 2. Resend completed")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[SEND] EXCEPTION: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)[:100]}")


def _resend_send_impl(file: UploadFile, campaign_name: str, template_id: int, sending_mode: str, resend_reason: str, db: Session, user):
    """Create a resend campaign and queue ALL targets from file (no duplicate check)."""
    print(f"[SEND] ========== START RESEND SEND ==========", flush=True)
    print(f"[SEND] Campaign: {campaign_name}, Template: {template_id}, Mode: {sending_mode}", flush=True)
    log.info(f"[IMPL] 1. Validating template {template_id}")

    # Validate template exists (reuse New Campaign's template system)
    template = db.get(EmailTemplate, template_id)
    if not template:
        log.warning(f"Template {template_id} not found")
        print(f"[SEND] ERROR: Template {template_id} not found", flush=True)
        raise HTTPException(status_code=404, detail="Email template not found")

    log.info(f"[IMPL] 2. Template validated: {template.name}")
    print(f"[SEND] Template OK: {template.name}", flush=True)

    try:
        print(f"[SEND] Parsing file: {file.filename}", flush=True)
        log.info(f"[IMPL] 3. Parsing file")
        rows, header_map = parse_file(file)
        print(f"[SEND] Parsed {len(rows)} rows from file", flush=True)
        log.info(f"[IMPL] 4. Successfully parsed {len(rows)} rows for send")

        if not rows:
            print(f"[SEND] ERROR: File has no rows after parsing!", flush=True)
    except ValueError as e:
        print(f"[SEND] ERROR parsing file: {e}", flush=True)
        log.warning(f"File parse error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[SEND] UNEXPECTED ERROR parsing: {type(e).__name__}: {e}", flush=True)
        log.error(f"Unexpected parse error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)[:100]}")

    if not rows:
        print(f"[SEND] ERROR: File has no rows - cannot create campaign", flush=True)
        log.info(f"No rows in file for campaign '{campaign_name}'")
        raise HTTPException(status_code=400, detail="File contains no contacts.")

    # Collect resend targets - ALL emails from file (no duplicate check, no history check)
    print(f"[SEND] Processing {len(rows)} rows to extract emails", flush=True)
    log.info(f"[SEND] Processing {len(rows)} rows from file")
    resend_targets = []
    position = 0

    for idx, mapped_row in enumerate(rows):
        try:
            email = extract_email_field(mapped_row)
            if not email:
                print(f"[SEND] Row {idx}: No email found. Data: {mapped_row}", flush=True)
                log.debug(f"Row {idx}: No email field found in {mapped_row}")
                continue
            print(f"[SEND] Row {idx}: Email found: {email}", flush=True)
            log.debug(f"Row {idx}: Found email {email}")

            # Resend campaign: add ALL emails, no history or duplicate check
            company = mapped_row.get('company_name') or 'Unknown'
            contact_person = mapped_row.get('contact_person')

            resend_targets.append({
                'position': position,
                'email': email,
                'company_name': str(company) if company else 'Unknown',
                'contact_person': str(contact_person) if contact_person else None,
                'resend_reason': resend_reason[:255] if resend_reason else None,
            })
            position += 1
            print(f"[SEND] Row {idx}: ADDED target #{position} - {email}", flush=True)
            log.debug(f"Email {email}: added to resend queue (no duplicate check)")

        except Exception as e:
            log.warning(f"Row {idx} processing error: {e}", exc_info=True)
            continue

    print(f"[SEND] Final: {len(resend_targets)} targets to queue", flush=True)

    if not resend_targets:
        print(f"[SEND] ERROR: No valid emails extracted from {len(rows)} rows!", flush=True)
        log.warning(f"No valid emails found for resend campaign '{campaign_name}'")
        raise HTTPException(
            status_code=400,
            detail="No valid email addresses found in this file."
        )

    # Create Campaign record (integrates with existing sender pipeline)
    log.info(f"[IMPL] 10. Creating campaign with template {template_id}")
    campaign = Campaign(
        name=campaign_name.strip() or "Untitled resend",
        template_id=template_id,  # USE SAME TEMPLATE AS NEW CAMPAIGN
        mode=SendMode.automatic if sending_mode == "automatic" else SendMode.manual,
        daily_limit=min(50, cm.HARD_DAILY_CAP),  # Resend respects same 50/day limit
        owner_id=user.id,
        status=CampaignStatus.draft,
        source_filename=file.filename,
    )
    log.info(f"[IMPL] 11. Campaign template set to {template_id}")
    db.add(campaign)
    db.flush()
    log.info(f"Created resend campaign ID {campaign.id}: '{campaign_name}'")

    # Create CampaignTarget rows for each resend recipient
    # Mark as is_resend_approved so duplicate check doesn't block them
    targets = [
        CampaignTarget(
            campaign_id=campaign.id,
            position=target['position'],
            company_name=target['company_name'],
            email=target['email'],
            contact_person=target['contact_person'],
            state=TargetState.pending,
            resend_reason=target['resend_reason'],
            is_resend_approved=True,  # Auto-approve resends to bypass duplicate check
            approved_by_id=user.id,
            approved_at=datetime.now(timezone.utc),
        )
        for target in resend_targets
    ]
    db.add_all(targets)
    db.flush()  # Flush to get target IDs
    log.info(f"[SEND] Created {len(targets)} CampaignTarget records for campaign {campaign.id}")

    # Log each resend to Outreach table (same as New Campaign)
    outreach_records = []
    for target in targets:
        # Combine template subject and body for message_sent field
        message_content = f"Subject: {template.subject or 'Email'}\n\n{template.body or 'Message'}"

        outreach = Outreach(
            email=target.email,
            company_name=target.company_name,
            contact_person=target.contact_person,
            country=target.country,
            contacted_on=datetime.now(timezone.utc).date(),
            contact_method=ContactMethod.email,
            message_sent=message_content,
            owner_id=user.id,
            status=OutreachStatus.waiting_reply,
            notes=f"Resent via campaign '{campaign_name}' ({sending_mode} mode). Reason: {resend_reason}",
        )
        outreach_records.append(outreach)

    db.add_all(outreach_records)

    # Record the resend event (same format as New Campaign "imported")
    cm.record(
        db,
        campaign.id,
        "imported",
        f"{len(resend_targets)} addresses for resend from {file.filename}. Mode: {sending_mode}. Reason: {resend_reason}",
    )

    db.commit()
    log.info(f"Queued {len(resend_targets)} targets for resend campaign '{campaign_name}'")
    log.info(f"[SEND] Campaign {campaign.id} committed with {len(targets)} targets")

    # Don't auto-start - let user start manually like New Campaign
    # Scheduler will pick up draft campaigns when user clicks Start

    # Verify targets were actually created and committed
    db.commit()  # Ensure transaction is fully committed
    db.refresh(campaign)  # Refresh campaign from DB
    target_count = db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign.id).count()
    print(f"[SEND] FINAL: Verified {target_count} targets in DB for campaign {campaign.id}", flush=True)
    log.info(f"[SEND] Verified {target_count} targets in database for campaign {campaign.id}")

    # Return campaign status snapshot to show correct counts
    status_snapshot = cm.snapshot(db, campaign)
    print(f"[SEND] Status snapshot: total={status_snapshot.get('total')}, remaining={status_snapshot.get('remaining')}", flush=True)

    # Auto-start if automatic mode - scheduler needs running status to send
    if sending_mode == "automatic":
        print(f"[SEND] Auto-starting campaign {campaign.id} for automatic sending", flush=True)
        try:
            campaign = cm.start(db, campaign)
            db.commit()
            print(f"[SEND] Campaign {campaign.id} started successfully", flush=True)
            status_snapshot = cm.snapshot(db, campaign)  # Refresh status after starting
        except Exception as e:
            print(f"[SEND] Failed to start campaign: {e}", flush=True)
            log.warning(f"Failed to auto-start campaign: {e}")

    return {
        'campaign_id': campaign.id,
        'campaign_name': campaign_name,
        'queued_count': target_count,  # Use verified count from DB
        'sending_mode': sending_mode,
        'resend_reason': resend_reason,
        'status': campaign.status.value if hasattr(campaign.status, 'value') else str(campaign.status),
        'total': status_snapshot.get('total'),  # Include snapshot for accurate display
        'remaining': status_snapshot.get('remaining'),
    }
