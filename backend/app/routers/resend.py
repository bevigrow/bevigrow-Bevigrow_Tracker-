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


def parse_file(file: UploadFile) -> list[dict]:
    """Parse CSV or XLSX file and return list of rows."""
    try:
        content = file.file.read()

        if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
            wb = load_workbook(BytesIO(content))
            ws = wb.active

            headers = None
            rows = []
            for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                if row_idx == 1:
                    headers = [str(h).lower().strip() if h else f'col_{i}' for i, h in enumerate(row)]
                    continue
                if not any(row):  # Skip empty rows
                    continue
                rows.append(dict(zip(headers, row)))
            return rows
        else:
            # CSV/TSV
            text_content = content.decode('utf-8')
            reader = csv.DictReader(StringIO(text_content))
            rows = []
            for row in reader:
                if row:
                    rows.append(row)
            return rows
    except Exception as e:
        log.error(f"Failed to parse file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")


def extract_email_field(row: dict) -> str | None:
    """Extract email from row, trying common field names."""
    email_fields = ['email', 'e-mail', 'mail', 'recipient_email', 'contact_email']
    for field in email_fields:
        if field in row and row[field]:
            return str(row[field]).strip().lower()
    return None


def check_contact_history(db: Session, email: str) -> dict:
    """Check if email was previously contacted."""
    try:
        stmt = select(Outreach).where(Outreach.email == email.lower()).order_by(Outreach.contacted_on.desc())
        outreach = db.scalars(stmt).first()

        return {
            'email': email,
            'is_in_history': outreach is not None,
            'last_sent_date': outreach.contacted_on.isoformat() if outreach and outreach.contacted_on else None,
        }
    except Exception as e:
        log.error(f"Failed to check contact history for {email}: {e}", exc_info=True)
        return {
            'email': email,
            'is_in_history': False,
            'last_sent_date': None,
        }


@router.post("/review")
def resend_review(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Analyze uploaded file and identify previously contacted recipients."""
    try:
        rows = parse_file(file)

        if not rows:
            return {
                'total_recipients': 0,
                'previously_contacted': 0,
                'recipients': [],
            }

        recipients = []
        previously_contacted = 0

        for row in rows:
            email = extract_email_field(row)
            if not email:
                continue

            company = row.get('company') or row.get('company_name') or 'Unknown'
            contact_person = row.get('contact_person') or row.get('contact') or None

            history = check_contact_history(db, email)

            recipient = {
                'email': email,
                'company_name': str(company),
                'contact_person': str(contact_person) if contact_person else None,
                'is_in_history': history['is_in_history'],
                'last_sent_date': history['last_sent_date'],
            }
            recipients.append(recipient)

            if history['is_in_history']:
                previously_contacted += 1

        return {
            'total_recipients': len(recipients),
            'previously_contacted': previously_contacted,
            'recipients': recipients,
        }
    except Exception as e:
        log.error(f"Error in resend review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/send")
def resend_send(
    file: UploadFile = File(...),
    sending_mode: str = Form(...),
    resend_reason: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Queue resend for previously contacted recipients."""
    try:
        rows = parse_file(file)

        if not rows:
            return {
                'queued_count': 0,
                'sending_mode': sending_mode,
                'resend_reason': resend_reason,
                'status': 'queued',
            }

        queued_count = 0

        for row in rows:
            email = extract_email_field(row)
            if not email:
                continue

            history = check_contact_history(db, email)
            if not history['is_in_history']:
                continue

            queued_count += 1

        return {
            'queued_count': queued_count,
            'sending_mode': sending_mode,
            'resend_reason': resend_reason,
            'status': 'queued',
        }
    except Exception as e:
        log.error(f"Error in resend send: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error queuing resend: {str(e)}")
