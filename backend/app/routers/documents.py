"""Proof uploads: quotations, invoices, POs, screenshots, sample photos."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Contact, DocType, Document, User
from ..schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
}
CHUNK = 1024 * 1024


def _safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{ext or 'unknown'}' is not allowed",
        )
    return ext


def _to_out(doc: Document) -> DocumentOut:
    return DocumentOut.model_validate(doc).model_copy(
        update={"download_url": f"/api/documents/{doc.id}/download"}
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    contact_id: int | None = None,
    doc_type: DocType | None = None,
    limit: int = Query(default=200, ge=1, le=500),
):
    stmt = select(Document).options(selectinload(Document.contact))
    if contact_id:
        stmt = stmt.where(Document.contact_id == contact_id)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    rows = db.scalars(stmt.order_by(Document.created_at.desc()).limit(limit)).all()
    return [_to_out(d) for d in rows]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    contact_id: int = Form(...),
    doc_type: DocType = Form(DocType.other),
    note: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    ext = _safe_extension(file.filename or "")
    stored_name = f"{uuid.uuid4().hex}{ext}"
    destination = UPLOAD_DIR / stored_name
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    size = 0
    try:
        with destination.open("wb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not store file: {exc}") from exc

    original = re.sub(r"[\r\n\t]", "", file.filename or stored_name)[:255]
    doc = Document(
        contact_id=contact.id,
        uploaded_by_id=user.id,
        doc_type=doc_type,
        original_name=original,
        stored_name=stored_name,
        content_type=file.content_type,
        size_bytes=size,
        note=note,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _to_out(doc)


@router.get("/{document_id}/download")
def download_document(
    document_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # stored_name is a server-generated uuid + validated extension, but resolve
    # and re-check containment so a tampered row can never escape UPLOAD_DIR.
    root = UPLOAD_DIR.resolve()
    path = (root / doc.stored_name).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="File is no longer available on disk")

    return FileResponse(
        path,
        media_type=doc.content_type or "application/octet-stream",
        filename=doc.original_name,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    root = UPLOAD_DIR.resolve()
    path = (root / doc.stored_name).resolve()
    if root in path.parents:
        path.unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
