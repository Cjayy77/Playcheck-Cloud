"""Thin Creem.io API client — no SDK dependency, just the three calls we use.

API shapes verified against docs.creem.io (2026-07):
- POST {base}/v1/checkouts        -> {"checkout_url": ...}
- POST {base}/v1/customers/billing -> {"customer_portal_link": ...}
- Webhooks: `creem-signature` header = HMAC-SHA256 hex of the raw body.
Set CREEM_API_BASE=https://test-api.creem.io for sandbox mode.
"""
import hashlib
import hmac

import requests
from django.conf import settings


class CreemNotConfigured(RuntimeError):
    pass


def _post(path: str, payload: dict) -> dict:
    if not settings.CREEM_API_KEY:
        raise CreemNotConfigured("Set CREEM_API_KEY to enable billing.")
    response = requests.post(
        f"{settings.CREEM_API_BASE}{path}",
        json=payload,
        headers={"x-api-key": settings.CREEM_API_KEY},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def create_checkout(org, success_url: str) -> str:
    """Returns the hosted checkout URL for the Team-tier product."""
    data = _post(
        "/v1/checkouts",
        {
            "product_id": settings.CREEM_PRODUCT_ID_TEAM,
            "request_id": f"org-{org.pk}",
            "success_url": success_url,
            "metadata": {"org_id": org.pk, "org_slug": org.slug},
        },
    )
    return data["checkout_url"]


def create_portal_link(customer_id: str) -> str:
    data = _post("/v1/customers/billing", {"customer_id": customer_id})
    return data["customer_portal_link"]


def signature_valid(raw_body: bytes, header_signature: str) -> bool:
    if not settings.CREEM_WEBHOOK_SECRET:
        # Explicitly unconfigured: only acceptable in DEBUG (local dev).
        return settings.DEBUG
    expected = hmac.new(
        settings.CREEM_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header_signature or "")
