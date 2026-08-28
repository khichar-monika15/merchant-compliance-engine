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


def _is_first_party(domain: str, page_domain: str) -> bool:
    if not domain:
        return True
    return domain == page_domain or domain.endswith("." + page_domain)


def check_sri(tag) -> dict:
    integrity = tag.get("integrity", "")
    crossorigin = tag.get("crossorigin", "")
    return {
        "has_sri": bool(integrity),
        "sri_hash": integrity or None,
        "crossorigin": crossorigin,
    }


def score_script_risk(domain: str, risk_db: dict) -> dict:
    if not domain:
        return {"risk_level": "low", "category": "unknown"}

    for entry in risk_db.get("low_risk", []):
        if isinstance(entry, dict):
            if any(domain.endswith(d) for d in entry.get("domains", [])):
                return {"risk_level": "low", "category": entry.get("category", "unknown")}
        elif domain.endswith(entry):
            return {"risk_level": "low", "category": "unknown"}

    for entry in risk_db.get("medium_risk", []):
        if isinstance(entry, dict):
            if any(domain.endswith(d) for d in entry.get("domains", [])):
                return {"risk_level": "medium", "category": entry.get("category", "tracking")}
        elif domain.endswith(entry):
            return {"risk_level": "medium", "category": "tracking"}

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
