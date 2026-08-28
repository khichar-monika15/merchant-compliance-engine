import re

from rapidfuzz import fuzz as rapidfuzz_fuzz

# (pattern, replacement, flags)
_NORMALIZATION_RULES: list[tuple[str, str, int]] = [
    (r"\bpvt\.?\s*", "private ", re.IGNORECASE),
    (r"\bltd\.?\s*$", "limited", re.IGNORECASE),
    (r"\s*&\s*", " and ", 0),
    (r"\bco\.?\s*$", "company", re.IGNORECASE),
    (r"\bintl\.?\s*", "international ", re.IGNORECASE),
    (r"\bllp\b", "limited liability partnership", re.IGNORECASE),
    (r"[.,]", "", 0),
    (r"\s+", " ", 0),
]

_KNOWN_MISMATCH_PATTERNS = [
    {
        "pattern": "& vs and",
        "detect": lambda a, b: ("&" in a and "and" in b.lower()) or ("&" in b and "and" in a.lower()),
    },
    {
        "pattern": "Pvt vs Private",
        "detect": lambda a, b: _has_abbrev_mismatch(a, b, "pvt", "private"),
    },
    {
        "pattern": "Ltd vs Limited",
        "detect": lambda a, b: _has_abbrev_mismatch(a, b, "ltd", "limited"),
    },
    {
        "pattern": "word spacing",
        "detect": lambda a, b: _has_spacing_diff(a, b),
    },
]


def _has_abbrev_mismatch(a: str, b: str, abbrev: str, full: str) -> bool:
    a_lower, b_lower = a.lower(), b.lower()
    return (abbrev in a_lower and full in b_lower) or (full in a_lower and abbrev in b_lower)


def _has_spacing_diff(a: str, b: str) -> bool:
    """Detect cases where words are merged in one name vs spaced in the other."""
    a_no_space = re.sub(r"\s+", "", a.lower())
    b_no_space = re.sub(r"\s+", "", b.lower())
    if a_no_space == b_no_space and a.lower().replace(" ", "") != b.lower().replace(" ", ""):
        return False
    # If removing spaces makes them equal but they looked different, that's a spacing issue
    return a_no_space == b_no_space and a.lower() != b.lower()


def normalize_name(name: str) -> str:
    result = name.strip().lower()
    for pattern, replacement, flags in _NORMALIZATION_RULES:
        result = re.sub(pattern, replacement, result, flags=flags)
    return result.strip()


def check_name_pair(name_a: str, name_b: str, label_a: str, label_b: str) -> dict:
    norm_a = normalize_name(name_a)
    norm_b = normalize_name(name_b)

    # WRatio combines multiple algorithms; handles word order, abbreviations, partial matches
    similarity = rapidfuzz_fuzz.WRatio(norm_a, norm_b) / 100.0

    issues: list[str] = []
    for mp in _KNOWN_MISMATCH_PATTERNS:
        if mp["detect"](name_a, name_b):
            issues.append(f"{mp['pattern']} mismatch between {label_a} and {label_b}")

    if similarity < 0.90 and not issues:
        issues.append(f"{label_a} '{name_a}' differs significantly from {label_b} '{name_b}'")

    # Any known mismatch pattern means KYC docs are not consistent, regardless of similarity
    is_match = similarity >= 0.90 and len(issues) == 0

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
