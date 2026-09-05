import re
from functools import partial

from rapidfuzz import fuzz as rapidfuzz_fuzz

from backend import knowledge

# RBI-006 defines how business names are normalized and how close counts as a match.
_CRITERIA = knowledge.quality_criteria("RBI-006")

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
    """Detect cases where words are merged in one name vs spaced in the other.

    Normalised first, unlike the abbreviation detectors. Those need the raw names, because
    normalisation is what erases the evidence they look for. This one needs the opposite: on the
    raw names an abbreviation difference hides the spacing, so 'FreshKart Pvt. Ltd.' against
    'Fresh Kart Private Limited' reported the wording and never mentioned that the bank account
    says 'Fresh Kart'.
    """
    a, b = normalize_name(a), normalize_name(b)
    a_no_space = re.sub(r"\s+", "", a)
    b_no_space = re.sub(r"\s+", "", b)
    return a_no_space == b_no_space and a != b


_DETECTORS = {
    "& vs and": _has_ampersand_mismatch,
    "Pvt vs Private": partial(_has_abbrev_mismatch, abbrev="pvt", full="private"),
    "Ltd vs Limited": partial(_has_abbrev_mismatch, abbrev="ltd", full="limited"),
    "Co vs Company": partial(_has_abbrev_mismatch, abbrev="co", full="company"),
    "Intl vs International": partial(_has_abbrev_mismatch, abbrev="intl", full="international"),
    "word spacing": _has_spacing_diff,
}


def _active_detectors() -> dict:
    """Only the patterns RBI-006 declares are run, in the order it declares them.

    Driving the list from the checklist rather than from this dict means removing a pattern from
    the knowledge base actually stops it being applied, instead of leaving the file and the
    behaviour disagreeing.
    """
    declared = _CRITERIA["known_mismatch_patterns"]
    missing = [name for name in declared if name not in _DETECTORS]
    if missing:
        raise ValueError(f"RBI-006 declares patterns with no detector: {missing}")
    return {name: _DETECTORS[name] for name in declared}


_MISMATCH_DETECTORS = _active_detectors()


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
        # Carried so the report can show what the merchant typed. Two names that normalise to the
        # same string can still be a mismatch, and then the normalised pair is the one piece of
        # evidence that does not explain the verdict.
        "raw_a": name_a,
        "raw_b": name_b,
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
