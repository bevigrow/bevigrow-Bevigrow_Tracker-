"""Resend Campaign endpoints: intentional resend to previously contacted recipients.

Integrates with the existing campaign sender pipeline. Creates campaigns that the
scheduler picks up and processes according to sending mode and daily limits.

Reuses New Campaign's template, placeholder, and sending components for full feature parity.
"""
from __future__ import annotations

import csv
import json
import logging
from io import StringIO, BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Outreach, Campaign, CampaignTarget, CampaignStatus, SendMode, TargetState, EmailTemplate
from ..services import campaigns as cm
from ..services import templating

log = logging.getLogger("bevigrow.resend")

router = APIRouter(prefix="/api/resend", tags=["resend"])


@router.get("/health")
def resend_health():
    """Health check for resend router."""
    print("[HEALTH] Resend router health check called", flush=True)
    return {"status": "ok", "router": "resend"}




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

    # Create a mock target for preview
    mock_target = CampaignTarget(
        id=0,
        campaign_id=0,
        position=0,
        email=email,
        company_name=company_name,
        contact_person=contact_person,
        country=country,
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
            "can_send": len(unfilled) == 0,
        }
    except Exception as e:
        log.error(f"Preview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


def parse_file(file: UploadFile) -> list[dict]:
    """Parse CSV or XLSX file and return list of rows."""
    print(f"[PARSE] START: {file.filename if file else 'None'}", flush=True)
    log.info(f"parse_file called for: {file.filename if file else 'None'}")
    try:
        if not file or not file.filename:
            print("[PARSE] ERROR: file or filename is None", flush=True)
            raise ValueError("No file provided")

        print(f"[PARSE] Reading file: {file.filename}", flush=True)
        content = file.file.read()
        print(f"[PARSE] Read {len(content)} bytes", flush=True)
        log.info(f"Read {len(content)} bytes from file")

        if not content:
            print("[PARSE] ERROR: Content is empty after read", flush=True)
            raise ValueError("File is empty")

        filename = file.filename.lower()

        if filename.endswith(('.xlsx', '.xls')):
            try:
                wb = load_workbook(BytesIO(content))
                ws = wb.active
                if not ws:
                    raise ValueError("Workbook has no sheets")

                headers = None
                rows = []
                for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                    if row_idx == 1:
                        headers = [str(h).lower().strip() if h else f'col_{i}' for i, h in enumerate(row)]
                        continue
                    if not any(row):
                        continue
                    rows.append(dict(zip(headers or [], row)))
                return rows
            except Exception as e:
                log.error(f"Excel parsing error: {e}", exc_info=True)
                raise ValueError(f"Excel file error: {str(e)}")
        else:
            try:
                text_content = content.decode('utf-8', errors='replace')
                reader = csv.DictReader(StringIO(text_content))
                if not reader.fieldnames:
                    raise ValueError("CSV has no headers")
                rows = [row for row in reader if row and any(row.values())]
                return rows
            except Exception as e:
                log.error(f"CSV parsing error: {e}", exc_info=True)
                raise ValueError(f"CSV file error: {str(e)}")
    except ValueError:
        raise
    except Exception as e:
        log.error(f"File parsing error: {e}", exc_info=True)
        raise ValueError(f"File parsing error: {str(e)}")


def extract_email_field(row: dict) -> str | None:
    """Extract email from row, trying common field names."""
    email_fields = ['email', 'e-mail', 'mail', 'recipient_email', 'contact_email', 'email_address']
    for field in email_fields:
        value = row.get(field)
        if value:
            return str(value).strip().lower()
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
    """Implementation of resend review logic."""
    print(f"[IMPL] START: file={file.filename}", flush=True)
    log.info(f"[IMPL] 1. Started for file: {file.filename}")

    # Parse file
    try:
        print(f"[IMPL] Calling parse_file", flush=True)
        log.info(f"[IMPL] 2. Calling parse_file")
        rows = parse_file(file)
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

    # Process each row
    for idx, row in enumerate(rows):
        try:
            email = extract_email_field(row)
            if not email:
                log.debug(f"Row {idx}: No email field found")
                continue

            company = (row.get('company') or row.get('company_name') or 'Unknown')
            contact_person = row.get('contact_person') or row.get('contact')

            # Check history
            try:
                history = check_contact_history(db, email)
                log.debug(f"Email {email}: is_in_history={history['is_in_history']}")
            except Exception as history_error:
                print(f"[IMPL] History check failed for {email}: {history_error}", flush=True)
                log.error(f"Failed to check history for {email}: {history_error}")
                history = {'email': email, 'is_in_history': False, 'last_sent_date': None}

            recipient = {
                'email': email,
                'company_name': str(company) if company else 'Unknown',
                'contact_person': str(contact_person) if contact_person else None,
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
    """Create a resend campaign and queue targets with existing sender pipeline."""
    log.info(f"[IMPL] 1. Validating template {template_id}")

    # Validate template exists (reuse New Campaign's template system)
    template = db.get(EmailTemplate, template_id)
    if not template:
        log.warning(f"Template {template_id} not found")
        raise HTTPException(status_code=404, detail="Email template not found")

    log.info(f"[IMPL] 2. Template validated: {template.name}")

    try:
        log.info(f"[IMPL] 3. Parsing file")
        rows = parse_file(file)
        log.info(f"[IMPL] 4. Successfully parsed {len(rows)} rows for send")
    except ValueError as e:
        log.warning(f"File parse error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    if not rows:
        log.info(f"No rows in file for campaign '{campaign_name}'")
        raise HTTPException(status_code=400, detail="File contains no contacts to resend.")

    # Collect resend targets (only previously contacted)
    resend_targets = []
    position = 0

    for idx, row in enumerate(rows):
        try:
            email = extract_email_field(row)
            if not email:
                log.debug(f"Row {idx}: No email field, skipping")
                continue

            # Check if email was previously contacted
            try:
                history = check_contact_history(db, email)
            except Exception as history_error:
                log.error(f"Failed to check history for {email}: {history_error}")
                continue

            if not history['is_in_history']:
                log.debug(f"Email {email}: not in history, skipping")
                continue

            # This is a target to resend to
            company = (row.get('company') or row.get('company_name') or 'Unknown')
            contact_person = row.get('contact_person') or row.get('contact')

            resend_targets.append({
                'position': position,
                'email': email,
                'company_name': str(company) if company else 'Unknown',
                'contact_person': str(contact_person) if contact_person else None,
                'resend_reason': resend_reason[:255] if resend_reason else None,  # Truncate to DB limit
            })
            position += 1
            log.debug(f"Email {email}: added to resend queue")

        except Exception as e:
            log.warning(f"Row {idx} processing error: {e}", exc_info=True)
            continue

    if not resend_targets:
        log.warning(f"No previously contacted recipients found for resend campaign '{campaign_name}'")
        raise HTTPException(
            status_code=400,
            detail="No previously contacted recipients found in this file."
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
    targets = [
        CampaignTarget(
            campaign_id=campaign.id,
            position=target['position'],
            company_name=target['company_name'],
            email=target['email'],
            contact_person=target['contact_person'],
            state=TargetState.pending,
            resend_reason=target['resend_reason'],
        )
        for target in resend_targets
    ]
    db.add_all(targets)

    # Record the resend event
    cm.record(
        db,
        campaign.id,
        "resend_created",
        f"Resend campaign for {len(resend_targets)} previously contacted recipients. Reason: {resend_reason}",
    )

    db.commit()
    log.info(f"Queued {len(resend_targets)} targets for resend campaign '{campaign_name}'")

    return {
        'campaign_id': campaign.id,
        'campaign_name': campaign_name,
        'queued_count': len(resend_targets),
        'sending_mode': sending_mode,
        'resend_reason': resend_reason,
        'status': 'draft',
    }
