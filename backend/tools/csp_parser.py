from __future__ import annotations

from functools import lru_cache

from backend import knowledge


@lru_cache(maxsize=1)
def _grading_bands() -> list[tuple[int, str]]:
    """CSP strength bands, highest first, from PCI-004 rather than hardcoded here.

    The thresholds existed in both places and happened to agree. That is what the crawler's
    URL patterns looked like before one of them lost `/money-back`.
    """
    grading = knowledge.pci_check("PCI-004")["grading"]
    bands = [(band["score_min"], name) for name, band in grading.items()]
    return sorted(bands, reverse=True)


def _strength_for(score: int) -> str:
    for minimum, name in _grading_bands():
        if score >= minimum:
            return name
    return "none"


def parse_csp(csp_string: str) -> dict[str, list[str]]:
    """Parse a Content-Security-Policy header into {directive: [values]}."""
    directives: dict[str, list[str]] = {}
    for part in csp_string.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if tokens:
            directives[tokens[0].lower()] = tokens[1:]
    return directives


def grade_csp(parsed: dict[str, list[str]]) -> dict:
    issues: list[str] = []
    score = 100

    if not parsed:
        return {"present": False, "policy": "", "strength": "none", "issues": ["CSP header missing"], "score": 0}

    # Check for dangerous values
    for directive, values in parsed.items():
        joined = " ".join(values).lower()
        if "'unsafe-inline'" in joined:
            issues.append(f"'unsafe-inline' in {directive} weakens XSS protection")
            score -= 25
        if "'unsafe-eval'" in joined:
            issues.append(f"'unsafe-eval' in {directive} allows arbitrary code execution")
            score -= 25
        if joined.strip() == "*":
            issues.append(f"Wildcard (*) in {directive} allows any source")
            score -= 20

    # Must-have directives
    for required in ("default-src", "script-src", "object-src"):
        if required not in parsed:
            issues.append(f"Missing {required} directive")
            score -= 10

    if "upgrade-insecure-requests" not in parsed:
        issues.append("upgrade-insecure-requests not set")
        score -= 5

    score = max(0, score)
    strength = _strength_for(score)

    return {
        "present": True,
        "directives": parsed,
        "strength": strength,
        "issues": issues,
        "score": score,
    }


def analyze_security_headers(headers: dict[str, str]) -> dict:
    """Analyze all security-relevant HTTP headers from a lowercase header dict."""
    lowered = {k.lower(): v for k, v in headers.items()}

    # CSP
    csp_raw = lowered.get("content-security-policy", "")
    csp_parsed = parse_csp(csp_raw) if csp_raw else {}
    csp_result = grade_csp(csp_parsed)

    # HSTS
    hsts_raw = lowered.get("strict-transport-security", "")
    hsts = {"present": bool(hsts_raw), "value": hsts_raw, "issues": []}
    if hsts_raw:
        if "max-age" not in hsts_raw.lower():
            hsts["issues"].append("HSTS missing max-age")
        elif "max-age=0" in hsts_raw.lower():
            hsts["issues"].append("HSTS max-age=0 effectively disables it")
        if "includesubdomains" not in hsts_raw.lower():
            hsts["issues"].append("HSTS missing includeSubDomains")
    else:
        hsts["issues"].append("HSTS header missing, HTTPS not enforced")

    # X-Frame-Options
    xfo_raw = lowered.get("x-frame-options", "")
    xfo = {"present": bool(xfo_raw), "value": xfo_raw, "issues": []}
    if not xfo_raw:
        xfo["issues"].append("X-Frame-Options missing, clickjacking risk")
    elif xfo_raw.upper() not in ("DENY", "SAMEORIGIN"):
        xfo["issues"].append(f"X-Frame-Options has unexpected value: {xfo_raw}")

    # X-Content-Type-Options
    xcto_raw = lowered.get("x-content-type-options", "")
    xcto = {"present": bool(xcto_raw), "value": xcto_raw, "issues": []}
    if xcto_raw.lower() != "nosniff":
        xcto["issues"].append("X-Content-Type-Options: nosniff not set")

    # Referrer-Policy
    rp_raw = lowered.get("referrer-policy", "")
    rp = {"present": bool(rp_raw), "value": rp_raw, "issues": []}
    if not rp_raw:
        rp["issues"].append("Referrer-Policy missing, may leak URLs to third parties")
    elif rp_raw.lower() in ("unsafe-url", "no-referrer-when-downgrade"):
        rp["issues"].append(f"Referrer-Policy '{rp_raw}' leaks full URL to third parties")

    return {
        "csp": csp_result,
        "hsts": hsts,
        "x_frame_options": xfo,
        "x_content_type": xcto,
        "referrer_policy": rp,
    }
