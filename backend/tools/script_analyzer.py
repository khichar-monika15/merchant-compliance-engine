from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_RISK_DB_PATH = Path(__file__).parent.parent / "knowledge" / "script_risk_database.json"
_risk_db: dict | None = None


def _load_risk_db() -> dict:
    global _risk_db
    if _risk_db is None:
        if _RISK_DB_PATH.exists():
            with _RISK_DB_PATH.open() as f:
                _risk_db = json.load(f)
        else:
            _risk_db = {"low_risk": [], "medium_risk": [], "high_risk_indicators": []}
    return _risk_db


def _extract_domain(src: str) -> str:
    try:
        return urlparse(src).netloc.lower()
    except Exception:
        return ""


def _registrable_domain(domain: str) -> str:
    """Strip a leading 'www.' so the apex and the www host are treated as one site."""
    domain = domain.lower().strip().rstrip(".")
    return domain[4:] if domain.startswith("www.") else domain


def _is_first_party(domain: str, page_domain: str) -> bool:
    """A merchant's own script is first-party whether it is served from the apex or a subdomain.

    Comparing raw hosts marked example.com as third-party on www.example.com, which inflated the
    third-party count and produced false 'PCI 6.4.3 integrity violation' gaps.
    """
    if not domain:
        return True  # inline script
    site = _registrable_domain(page_domain)
    host = _registrable_domain(domain)
    if not site:
        return False
    return host == site or host.endswith("." + site)


def check_sri(tag) -> dict:
    integrity = tag.get("integrity", "")
    crossorigin = tag.get("crossorigin", "")
    return {
        "has_sri": bool(integrity),
        "sri_hash": integrity or None,
        "crossorigin": crossorigin,
    }


def score_script_risk(domain: str, risk_db: dict) -> dict:
    """Classify a script's domain, preferring the most specific declared match.

    First-wins matching meant a broad entry shadowed a narrow one: `googleapis.com` is declared
    as "google" and `fonts.googleapis.com` as "fonts", so whichever came first in the file
    decided, and the fonts category could never be produced.
    """
    if not domain:
        return {"risk_level": "low", "category": "unknown"}

    tiers = (
        ("low", risk_db.get("low_risk", []), "unknown"),
        ("medium", risk_db.get("medium_risk", []), "tracking"),
    )

    best: tuple[int, str, str] | None = None
    for risk_level, entries, default_category in tiers:
        for entry in entries:
            if isinstance(entry, dict):
                domains = entry.get("domains", [])
                category = entry.get("category", default_category)
            else:
                domains, category = [entry], default_category
            for declared in domains:
                if domain == declared or domain.endswith("." + declared):
                    if best is None or len(declared) > best[0]:
                        best = (len(declared), risk_level, category)

    if best is not None:
        return {"risk_level": best[1], "category": best[2]}

    for indicator in risk_db.get("high_risk_indicators", []):
        if indicator in domain:
            return {"risk_level": "high", "category": "unknown"}

    return {"risk_level": "medium", "category": "unknown"}


def extract_scripts(html: str, page_url: str) -> list[dict]:
    try:
        page_domain = urlparse(page_url).netloc.lower()
    except Exception:
        page_domain = ""

    soup = BeautifulSoup(html, "lxml")
    risk_db = _load_risk_db()
    scripts: list[dict] = []

    for tag in soup.find_all("script"):
        src = tag.get("src")
        if src:
            domain = _extract_domain(src)
            first_party = _is_first_party(domain, page_domain)
            sri_info = check_sri(tag)
            risk_info = score_script_risk(domain, risk_db) if not first_party else {"risk_level": "low", "category": "first-party"}
            scripts.append({
                "src": src,
                "domain": domain,
                "has_sri": sri_info["has_sri"],
                "sri_hash": sri_info["sri_hash"],
                "is_inline": False,
                "is_first_party": first_party,
                "risk_level": risk_info["risk_level"],
                "category": risk_info["category"],
            })
        else:
            # Inline script
            scripts.append({
                "src": None,
                "domain": None,
                "has_sri": False,
                "sri_hash": None,
                "is_inline": True,
                "is_first_party": True,
                "risk_level": "low",
                "category": "inline",
            })

    return scripts
