"""Proof uploads: quotations, invoices, POs, screenshots, sample photos.

Files are stored as bytes in the database rather than on disk. Render's free
instances rebuild their filesystem on every deploy, so anything written there
vanishes and the document row is left pointing at a file that no longer
exists — which is exactly what happened to the first uploads.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Contact, DocType, Document, User
from ..schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
}
CHUNK = 512 * 1024


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
    # Deliberately does not load `content` — listing a hundred documents must
    # not pull a hundred files across the wire.
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

    _safe_extension(file.filename or "")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    # Read in chunks so an oversized upload is rejected before it is all in
    # memory, rather than after.
    parts: list[bytes] = []
    size = 0
    while chunk := await file.read(CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit",
            )
        parts.append(chunk)

    if not size:
        raise HTTPException(status_code=400, detail="That file is empty")

    original = re.sub(r"[\r\n\t]", "", file.filename or "upload")[:255]
    doc = Document(
        contact_id=contact.id,
        uploaded_by_id=user.id,
        doc_type=doc_type,
        original_name=original,
        stored_name="",
        content=b"".join(parts),
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

    if not doc.content:
        # Written before files moved into the database, and lost with the
        # container that held them.
        raise HTTPException(
            status_code=410,
            detail="This file was uploaded before files were stored durably and "
            "is no longer available. Please upload it again.",
        )

    return Response(
        content=doc.content,
        media_type=doc.content_type or "application/octet-stream",
        headers={
            # `filename*` carries the UTF-8 name for anything non-ASCII.
            "Content-Disposition": f'attachment; filename="{doc.original_name}"',
            "Content-Length": str(len(doc.content)),
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
