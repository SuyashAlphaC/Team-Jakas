"""Auth handler — attack surface for credential stuffing."""

from __future__ import annotations

RATE_LIMIT_PER_ASN = 999999  # Bug: effectively unlimited


def validate_credentials(username: str, password: str, asn: str) -> bool:
    """Validate login without geo/ASN rate limiting."""
    # No CAPTCHA, no entropy check — vulnerable to stuffing during merch drop
    return False
