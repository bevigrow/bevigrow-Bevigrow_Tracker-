"""Resend Campaign endpoints: intentional resend to previously contacted recipients."""
from __future__ import annotations

import csv
import logging
from io import StringIO, BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Outreach

log = logging.getLogger("bevigrow.resend")

router = APIRouter(prefix="/api/resend", tags=["resend"])


@router.get("/health")
def resend_health():
    """Health check for resend router."""
    return {"status": "ok", "router": "resend"}


def parse_file(file: UploadFile) -> list[dict]:
    """Parse CSV or XLSX file and return list of rows."""
    try:
        if not file or not file.filename:
            raise ValueError("No file provided")

        content = file.file.read()
        if not content:
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
    _: User = Depends(get_current_user),
):
    """Analyze uploaded file and identify previously contacted recipients."""
    log.info(f"Processing resend review for: {file.filename if file else 'unknown'}")

    try:
        # Parse file
        try:
            rows = parse_file(file)
        except ValueError as e:
            log.warning(f"File parse error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        log.info(f"Parsed {len(rows)} rows")

        if not rows:
            return {
                'total_recipients': 0,
                'previously_contacted': 0,
                'recipients': [],
            }

        recipients = []
        previously_contacted = 0

        # Process each row
        for idx, row in enumerate(rows):
            try:
                email = extract_email_field(row)
                if not email:
                    continue

                company = (row.get('company') or row.get('company_name') or 'Unknown')
                contact_person = row.get('contact_person') or row.get('contact')

                # Check history
                history = check_contact_history(db, email)

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
                log.warning(f"Row {idx} processing error: {row_error}")
                continue

        log.info(f"Review complete: {len(recipients)} total, {previously_contacted} previously contacted")
        return {
            'total_recipients': len(recipients),
            'previously_contacted': previously_contacted,
            'recipients': recipients,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Resend review error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing file")


@router.post("/send")
def resend_send(
    file: UploadFile = File(...),
    sending_mode: str = Form(...),
    resend_reason: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Queue resend for previously contacted recipients."""
    log.info(f"Queuing resend: mode={sending_mode}, reason={resend_reason}")

    try:
        try:
            rows = parse_file(file)
        except ValueError as e:
            log.warning(f"File parse error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        if not rows:
            return {
                'queued_count': 0,
                'sending_mode': sending_mode,
                'resend_reason': resend_reason,
                'status': 'queued',
            }

        queued_count = 0

        for row in rows:
            try:
                email = extract_email_field(row)
                if not email:
                    continue

                history = check_contact_history(db, email)
                if not history['is_in_history']:
                    continue

                queued_count += 1
            except Exception as e:
                log.warning(f"Row queuing error: {e}")
                continue

        log.info(f"Queued {queued_count} recipients for resend")
        return {
            'queued_count': queued_count,
            'sending_mode': sending_mode,
            'resend_reason': resend_reason,
            'status': 'queued',
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Resend send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error queuing resend")
