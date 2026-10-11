import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from constants import ACCESS_TOKEN_SECRET, ACCESS_TOKEN_TTL_SECONDS


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    kind: str
    subject: str


class InvalidAccessToken(ValueError):
    pass


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(kind: str, subject: str, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = {
        "exp": issued_at + ACCESS_TOKEN_TTL_SECONDS,
        "iat": issued_at,
        "kind": kind,
        "sub": subject,
    }
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(ACCESS_TOKEN_SECRET.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256)
    return f"{encoded_payload}.{_encode(signature.digest())}"


def verify_access_token(token: str, now: int | None = None) -> AuthenticatedPrincipal:
    try:
        encoded_payload, encoded_signature = token.split(".")
        expected = hmac.new(
            ACCESS_TOKEN_SECRET.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_decode(encoded_signature), expected):
            raise InvalidAccessToken()
        payload = json.loads(_decode(encoded_payload))
        current_time = int(time.time() if now is None else now)
        if not isinstance(payload, dict) or payload.get("exp", 0) <= current_time:
            raise InvalidAccessToken()
        if payload.get("kind") not in ("PF", "REPRESENTATIVE"):
            raise InvalidAccessToken()
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidAccessToken()
        return AuthenticatedPrincipal(kind=payload["kind"], subject=subject)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error) as exception:
        raise InvalidAccessToken() from exception
