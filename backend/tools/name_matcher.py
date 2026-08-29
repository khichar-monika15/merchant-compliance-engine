import json
import re
from functools import partial
from pathlib import Path

from rapidfuzz import fuzz as rapidfuzz_fuzz

_RBI_DB_PATH = Path(__file__).parent.parent / "knowledge" / "rbi_mdd_checklist.json"


def _rbi_006() -> dict:
    """RBI-006 defines how business names are normalized and how close counts as a match."""
    with _RBI_DB_PATH.open() as f:
        checks = json.load(f)["checks"]
    return next(c for c in checks if c["id"] == "RBI-006")["quality_criteria"]


_CRITERIA = _rbi_006()

# (compiled pattern, replacement)
_NORMALIZATION_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r["pattern"], re.IGNORECASE if r.get("ignore_case") else 0), r["replacement"])
    for r in _CRITERIA["normalization_rules"]
]

_SIMILARITY_THRESHOLD: float = _CRITERIA["min_similarity_threshold"]


def _has_ampersand_mismatch(a: str, b: str) -> bool:
    """One document uses '&' where the other spells out 'and', but they are otherwise the same name."""
    if ("&" in a) == ("&" in b):
        return False
    return normalize_name(a) == normalize_name(b)


def _has_abbrev_mismatch(a: str, b: str, abbrev: str, full: str) -> bool:
    """One document abbreviates where the other spells the word out.

    Matched on whole words: a bare substring test flags 'Cotton Company Ltd' against 'Cotton
    Company Limited' as a Co/Company mismatch, because 'co' sits inside both 'Cotton' and
    'Company'.
    """
    def has(word: str, text: str) -> bool:
        return re.search(rf"\b{re.escape(word)}\b\.?", text, re.IGNORECASE) is not None

    return (has(abbrev, a) and has(full, b)) or (has(full, a) and has(abbrev, b))


def _has_spacing_diff(a: str, b: str) -> bool:
    """Detect cases where words are merged in one name vs spaced in the other."""
    a_no_space = re.sub(r"\s+", "", a.lower())
    b_no_space = re.sub(r"\s+", "", b.lower())
    return a_no_space == b_no_space and a.lower() != b.lower()


# Keyed by the pattern names RBI-006 declares, so a pattern added to the checklist without a
# detector here fails a test rather than being silently ignored.
_MISMATCH_DETECTORS = {
    "& vs and": _has_ampersand_mismatch,
    "Pvt vs Private": partial(_has_abbrev_mismatch, abbrev="pvt", full="private"),
    "Ltd vs Limited": partial(_has_abbrev_mismatch, abbrev="ltd", full="limited"),
    "Co vs Company": partial(_has_abbrev_mismatch, abbrev="co", full="company"),
    "Intl vs International": partial(_has_abbrev_mismatch, abbrev="intl", full="international"),
    "word spacing": _has_spacing_diff,
}


def normalize_name(name: str) -> str:
    result = name.strip().lower()
    for pattern, replacement in _NORMALIZATION_RULES:
        result = pattern.sub(replacement, result)
    return result.strip()


def check_name_pair(name_a: str, name_b: str, label_a: str, label_b: str) -> dict:
    norm_a = normalize_name(name_a)
    norm_b = normalize_name(name_b)

    # WRatio combines multiple algorithms; handles word order, abbreviations, partial matches
    similarity = rapidfuzz_fuzz.WRatio(norm_a, norm_b) / 100.0

    issues: list[str] = []
    # Identical documents cannot disagree — only compare spellings when the raw names differ
    if name_a.strip().lower() != name_b.strip().lower():
        for name, detect in _MISMATCH_DETECTORS.items():
            if detect(name_a, name_b):
                issues.append(f"{name} mismatch between {label_a} and {label_b}")

    if similarity < _SIMILARITY_THRESHOLD and not issues:
        issues.append(f"{label_a} '{name_a}' differs significantly from {label_b} '{name_b}'")

    # Any known mismatch pattern means KYC docs are not consistent, regardless of similarity
    is_match = similarity >= _SIMILARITY_THRESHOLD and len(issues) == 0

    return {
        "match": is_match,
        "similarity": round(similarity, 4),
        "normalized_a": norm_a,
        "normalized_b": norm_b,
        "issues": issues,
    }


def validate_kyc_consistency(pan_name: str, gst_name: str, bank_name: str) -> dict:
    pan_gst = check_name_pair(pan_name, gst_name, "PAN", "GST")
    gst_bank = check_name_pair(gst_name, bank_name, "GST", "Bank")
    pan_bank = check_name_pair(pan_name, bank_name, "PAN", "Bank")

    all_issues = pan_gst["issues"] + gst_bank["issues"] + pan_bank["issues"]
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for issue in all_issues:
        if issue not in seen:
            seen.add(issue)
            deduped.append(issue)

    overall = all(m["match"] for m in [pan_gst, gst_bank, pan_bank])
    confidence = min(pan_gst["similarity"], gst_bank["similarity"], pan_bank["similarity"])

    return {
        "pan_gst_match": pan_gst,
        "gst_bank_match": gst_bank,
        "pan_bank_match": pan_bank,
        "common_mismatches": deduped,
        "overall_consistent": overall,
        "confidence": round(confidence, 4),
    }
