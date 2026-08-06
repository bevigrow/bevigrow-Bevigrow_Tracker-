"""Authentication: password login, Google sign-in, signup, password reset,
profile, and user administration."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import AuthProvider, Role, User
from ..schemas import (
    AdminResetPasswordRequest,
    AuthConfigOut,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLoginRequest,
    LoginRequest,
    ProfileUpdate,
    ResetPasswordRequest,
    SignupRequest,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..security import create_access_token, hash_password, verify_password
from ..services import mailer
from ..services.google_auth import GoogleAuthError, verify_google_token

log = logging.getLogger("bevigrow.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

# Shown for both "no such account" and "wrong password" so the endpoint cannot
# be used to discover which email addresses are registered.
INVALID_CREDENTIALS = "Incorrect email or password"


def _issue(db: Session, user: User) -> Token:
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, {"role": user.role.value, "email": user.email})
    return Token(access_token=token, user=UserOut.model_validate(user))


def _hash_token(raw: str) -> str:
    """Reset tokens are stored hashed — a leaked table must not be replayable."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _default_role() -> Role:
    try:
        return Role(settings.DEFAULT_SIGNUP_ROLE)
    except ValueError:
        return Role.employee


# --------------------------------------------------------------- public config


@router.get("/config", response_model=AuthConfigOut)
def auth_config() -> AuthConfigOut:
    """What the login page should offer. Safe to call unauthenticated.

    The Google client ID is public by design — it identifies the app to
    Google and is embedded in every browser sign-in flow. The client *secret*
    is never used here, because ID-token verification does not need one.
    """
    return AuthConfigOut(
        google_enabled=settings.google_enabled,
        google_client_id=settings.GOOGLE_CLIENT_ID.strip(),
        self_signup_enabled=settings.ALLOW_SELF_SIGNUP,
        password_reset_enabled=True,
        allowed_email_domains=settings.allowed_domains,
    )


# ----------------------------------------------------------------- password


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    return _issue(db, _authenticate(db, payload.email, payload.password))


@router.post("/token", response_model=Token, include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    """OAuth2 password flow, used by the interactive /docs page."""
    return _issue(db, _authenticate(db, form.username, form.password))


# ------------------------------------------------------------------- google


@router.post("/google", response_model=Token)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> Token:
    try:
        identity = verify_google_token(payload.credential)
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if not settings.email_domain_allowed(identity.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That email domain is not permitted to access BeviGrow.",
        )

    # Match on the Google subject first — it is stable even if the user
    # changes their email address at Google.
    user = db.scalar(select(User).where(User.google_sub == identity.sub))

    if user is None:
        # Fall back to email so an invited account can be claimed. Safe only
        # because verify_google_token rejects unverified addresses.
        user = db.scalar(select(User).where(User.email == identity.email))
        if user is not None:
            user.google_sub = identity.sub

    if user is None:
        if not settings.ALLOW_SELF_SIGNUP:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No BeviGrow account exists for that Google address. "
                "Ask your administrator for an invitation.",
            )
        user = User(
            name=identity.name,
            email=identity.email,
            hashed_password="",
            role=_default_role(),
            auth_provider=AuthProvider.google,
            google_sub=identity.sub,
        )
        db.add(user)
        log.info("Created account from Google sign-in: %s", identity.email)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    if identity.picture:
        user.avatar_url = identity.picture
    db.flush()
    return _issue(db, user)


# ------------------------------------------------------------------- signup


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> Token:
    if not settings.ALLOW_SELF_SIGNUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self sign-up is disabled. Ask your administrator for an invitation.",
        )

    email = payload.email.lower().strip()
    if not settings.email_domain_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That email domain is not permitted to access BeviGrow.",
        )
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists. Try signing in.",
        )

    user = User(
        name=payload.name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=_default_role(),
        auth_provider=AuthProvider.password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue(db, user)


# ----------------------------------------------------------- password reset


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always reports the same thing, whether or not the account exists."""
    generic = ForgotPasswordResponse(
        message="If an account exists for that address, a reset link is on its way.",
        email_sent=settings.smtp_enabled,
    )

    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None or not user.is_active:
        return generic

    raw_token = secrets.token_urlsafe(32)
    user.reset_token_hash = _hash_token(raw_token)
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.RESET_TOKEN_TTL_MINUTES
    )
    db.commit()

    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={raw_token}"
    mailer.send_reset_email(user.email, user.name, reset_url)
    return generic


@router.post("/reset-password", response_model=Token)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.reset_token_hash == _hash_token(payload.token)))
    if user is None:
        raise HTTPException(status_code=400, detail="That reset link is invalid or has already been used.")

    expires = user.reset_token_expires
    if expires is None:
        raise HTTPException(status_code=400, detail="That reset link is invalid or has already been used.")
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="That reset link has expired. Request a new one.")

    user.hashed_password = hash_password(payload.new_password)
    # Single use.
    user.reset_token_hash = None
    user.reset_token_expires = None
    if user.auth_provider == AuthProvider.google:
        user.auth_provider = AuthProvider.password
    db.commit()
    db.refresh(user)
    return _issue(db, user)


# ------------------------------------------------------------------ profile


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """Users edit their own name only — never their own role or status."""
    if payload.name is not None:
        user.name = payload.name.strip()
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", response_model=UserOut)
def change_own_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if user.hashed_password and not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")
    user.hashed_password = hash_password(payload.new_password)
    user.auth_provider = AuthProvider.password
    db.commit()
    db.refresh(user)
    return user


# -------------------------------------------------------------------- users


@users_router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Match on name or email"),
    role: Role | None = None,
    is_active: bool | None = None,
):
    stmt = select(User)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.name).like(needle), func.lower(User.email).like(needle))
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    return db.scalars(stmt.order_by(User.created_at.desc())).all()


@users_router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> User:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A user with that email already exists"
        )
    user = User(
        name=payload.name.strip(),
        email=email,
        role=payload.role,
        hashed_password=hash_password(payload.password),
        auth_provider=AuthProvider.password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if password := data.pop("password", None):
        user.hashed_password = hash_password(password)
    # An admin must not be able to lock themselves out of their own instance.
    if data.get("is_active") is False and user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if "role" in data and user.id == admin.id and data["role"] != Role.admin:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@users_router.post("/{user_id}/reset-password", response_model=UserOut)
def admin_reset_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    """Set a password directly. Used when no mail provider is configured."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(payload.new_password)
    user.auth_provider = AuthProvider.password
    user.reset_token_hash = None
    user.reset_token_expires = None
    db.commit()
    db.refresh(user)
    return user


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == Role.admin:
        remaining = db.scalar(
            select(func.count(User.id)).where(User.role == Role.admin, User.id != user_id)
        )
        if not remaining:
            raise HTTPException(
                status_code=400, detail="You cannot delete the last remaining administrator"
            )
    db.delete(user)
    db.commit()
