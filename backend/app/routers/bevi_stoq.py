"""Bevi Stoq inventory management API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User

router = APIRouter(prefix="/api/bevi-stoq", tags=["bevi-stoq"])


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "module": "bevi-stoq"}
