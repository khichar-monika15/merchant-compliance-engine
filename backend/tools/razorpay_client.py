from __future__ import annotations

import hashlib
import hmac

import razorpay

from backend.config import get_settings


def _client() -> razorpay.Client:
    settings = get_settings()
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_order(amount_paise: int = 100, currency: str = "INR", notes: dict | None = None) -> dict:
    """Create a test-mode Razorpay order. Returns order dict or error dict."""
    try:
        client = _client()
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "notes": notes or {"purpose": "MCIE test payment"},
        }
        order = client.order.create(payload)
        return {"success": True, "order_id": order["id"], "amount": order["amount"], "currency": order["currency"]}
    except Exception as e:
        return {"success": False, "order_id": None, "error": str(e)}


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature using HMAC-SHA256."""
    settings = get_settings()
    expected = hmac.new(
        settings.razorpay_key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
