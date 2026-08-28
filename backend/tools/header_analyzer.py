from __future__ import annotations


SECURITY_HEADERS = {
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "x-xss-protection",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
}


def normalize_headers(raw: dict) -> dict[str, str]:
    """Lowercase all header keys."""
    return {k.lower(): v for k, v in raw.items()}


def extract_security_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return only the security-relevant headers from a normalized header dict."""
    normalized = normalize_headers(headers)
    return {k: v for k, v in normalized.items() if k in SECURITY_HEADERS}


def summarize_headers(headers: dict[str, str]) -> dict:
    """Return a quick presence summary for all security headers."""
    normalized = normalize_headers(headers)
    return {
        header: {"present": header in normalized, "value": normalized.get(header, "")}
        for header in sorted(SECURITY_HEADERS)
    }
