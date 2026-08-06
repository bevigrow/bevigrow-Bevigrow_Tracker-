"""Verification of Google Identity Services ID tokens.

The browser hands us a signed JWT from Google. It is never trusted as-is —
every check below has to pass:

  * the RS256 signature, against Google's published public keys (JWKS)
  * the audience, which must be *our* client ID. Without this, a token minted
    for any other website would be accepted here and anyone could sign in as
    anyone
  * the issuer, expiry, and that Google says the email is verified

Implemented on PyJWT's JWKS client rather than `google-auth`, which drags in
`requests` for one HTTP call. PyJWT fetches and caches the keys using the
standard library, so this adds no dependency.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from ..config import settings

log = logging.getLogger("bevigrow.google")

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

# Keys are cached in-process; Google rotates them infrequently.
_jwks_client: PyJWKClient | None = None


def _client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URI, cache_keys=True, lifespan=3600)
    return _jwks_client


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str
    picture: str | None
    email_verified: bool


class GoogleAuthError(Exception):
    """Raised when a token is missing, malformed, or fails verification."""


def verify_google_token(credential: str) -> GoogleIdentity:
    if not settings.google_enabled:
        raise GoogleAuthError("Google sign-in is not configured on this server.")
    if not credential or not credential.strip():
        raise GoogleAuthError("No Google credential was supplied.")

    try:
        signing_key = _client().get_signing_key_from_jwt(credential)
        claims = jwt.decode(
            credential,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID.strip(),
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise GoogleAuthError("That Google sign-in has expired. Please try again.") from exc
    except jwt.InvalidAudienceError as exc:
        # The token was minted for a different application.
        log.warning("Google token rejected: wrong audience")
        raise GoogleAuthError("That Google sign-in was not issued for BeviGrow.") from exc
    except jwt.PyJWTError as exc:
        log.warning("Google token rejected: %s", exc)
        raise GoogleAuthError("That Google sign-in could not be verified.") from exc
    except Exception as exc:  # network failure fetching the JWKS
        log.error("Could not verify Google token: %s", exc)
        raise GoogleAuthError("Could not reach Google to verify your sign-in.") from exc

    if claims.get("iss") not in _ISSUERS:
        raise GoogleAuthError("That Google sign-in came from an unexpected issuer.")

    email = (claims.get("email") or "").lower().strip()
    if not email:
        raise GoogleAuthError("Google did not return an email address.")

    # An unverified address proves nothing about who owns the mailbox, so it
    # must never be allowed to match an existing account by email.
    if not claims.get("email_verified", False):
        raise GoogleAuthError("Your Google email address is not verified.")

    sub = claims.get("sub")
    if not sub:
        raise GoogleAuthError("Google did not return an account identifier.")

    return GoogleIdentity(
        sub=str(sub),
        email=email,
        name=(claims.get("name") or email.split("@")[0]).strip(),
        picture=claims.get("picture"),
        email_verified=True,
    )
