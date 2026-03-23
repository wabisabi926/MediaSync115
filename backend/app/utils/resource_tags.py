"""
Extract resolution and format tags from resource metadata.

Tags are derived from resource_name, title, and existing quality/resolution fields.
"""

import re
from typing import Any

# ── Resolution definitions (order = priority high→low) ──────────────
RESOLUTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("4K",    re.compile(r"\b(?:4K|2160[pPiI]|UHD)\b", re.IGNORECASE)),
    ("1080p", re.compile(r"\b(?:1080[pPiI]|FHD|Full\s*HD)\b", re.IGNORECASE)),
    ("720p",  re.compile(r"\b720[pPiI]\b", re.IGNORECASE)),
    ("480p",  re.compile(r"\b480[pPiI]\b", re.IGNORECASE)),
]

# ── Format definitions ───────────────────────────────────────────────
FORMAT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Dolby Vision", re.compile(r"\b(?:Dolby\s*Vision|DoVi|DV)\b", re.IGNORECASE)),
    ("HDR10+",       re.compile(r"\bHDR10\+", re.IGNORECASE)),
    ("HDR10",        re.compile(r"\bHDR10\b", re.IGNORECASE)),
    ("HDR",          re.compile(r"\bHDR\b", re.IGNORECASE)),
    ("SDR",          re.compile(r"\bSDR\b", re.IGNORECASE)),
    ("REMUX",        re.compile(r"\bREMUX\b", re.IGNORECASE)),
    ("BluRay",       re.compile(r"\b(?:Blu[\-\s]?Ray|BDRip|BDRemux|BD)\b", re.IGNORECASE)),
    ("WEB-DL",       re.compile(r"\b(?:WEB[\-\s]?DL|WEBDL|WEBRip|WEB)\b", re.IGNORECASE)),
    ("HEVC",         re.compile(r"\b(?:HEVC|[Hh]\.?265|x265)\b")),
    ("H.264",        re.compile(r"\b(?:AVC|[Hh]\.?264|x264)\b")),
    ("Atmos",        re.compile(r"\bAtmos\b", re.IGNORECASE)),
    ("DTS-HD",       re.compile(r"\bDTS[\-\s]?HD(?:\s*MA)?\b", re.IGNORECASE)),
    ("TrueHD",       re.compile(r"\bTrueHD\b", re.IGNORECASE)),
    ("DTS",          re.compile(r"\bDTS\b", re.IGNORECASE)),
    ("AAC",          re.compile(r"\bAAC\b", re.IGNORECASE)),
    ("FLAC",         re.compile(r"\bFLAC\b", re.IGNORECASE)),
]

ALL_RESOLUTION_LABELS = [label for label, _ in RESOLUTION_PATTERNS]
ALL_FORMAT_LABELS = [label for label, _ in FORMAT_PATTERNS]


def _collect_text(resource: dict[str, Any]) -> str:
    """Build a searchable text blob from all relevant resource fields."""
    parts: list[str] = []
    for key in ("resource_name", "title", "name", "overview"):
        val = resource.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)

    # HDHive structured fields
    for key in ("quality", "resolution"):
        val = resource.get(key)
        if isinstance(val, list):
            parts.extend(str(v) for v in val if v)
        elif isinstance(val, str) and val.strip():
            parts.append(val)

    return " ".join(parts)


def extract_tags(resource: dict[str, Any]) -> dict[str, Any]:
    """
    Return ``{"resolution": "1080p"|"", "formats": ["HDR", "HEVC", ...]}``.

    Only the *highest-priority* resolution is returned; formats can be multiple.
    """
    text = _collect_text(resource)

    resolution = ""
    for label, pattern in RESOLUTION_PATTERNS:
        if pattern.search(text):
            resolution = label
            break

    formats: list[str] = []
    seen: set[str] = set()
    for label, pattern in FORMAT_PATTERNS:
        if label in seen:
            continue
        if pattern.search(text):
            formats.append(label)
            seen.add(label)
            # Avoid duplicate HDR variants
            if label in ("HDR10+", "HDR10"):
                seen.add("HDR")
            elif label == "DTS-HD":
                seen.add("DTS")

    return {"resolution": resolution, "formats": formats}


def enrich_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Add ``_tags`` field to a resource dict (in-place and returned)."""
    resource["_tags"] = extract_tags(resource)
    return resource


def score_resource(
    resource: dict[str, Any],
    preferred_resolutions: list[str],
    preferred_formats: list[str],
) -> float:
    """
    Score a resource based on user preferences.  Higher = better match.

    - Resolution match: 1000 * (N - index) where N = len(preferred_resolutions)
    - Format match: 100 per matching format (earlier in pref list → higher)
    - No match → 0 (still usable, just lower priority)
    """
    tags = resource.get("_tags") or extract_tags(resource)
    score = 0.0

    res = tags.get("resolution", "")
    if res and preferred_resolutions:
        res_lower = res.lower()
        for idx, pref in enumerate(preferred_resolutions):
            if pref.lower() == res_lower:
                score += 1000 * (len(preferred_resolutions) - idx)
                break

    formats = set(f.lower() for f in (tags.get("formats") or []))
    if formats and preferred_formats:
        for idx, pref in enumerate(preferred_formats):
            if pref.lower() in formats:
                score += 100 * (len(preferred_formats) - idx)

    return score


def sort_by_preference(
    resources: list[dict[str, Any]],
    preferred_resolutions: list[str],
    preferred_formats: list[str],
) -> list[dict[str, Any]]:
    """Sort resources by preference score (highest first), preserving order for ties."""
    if not preferred_resolutions and not preferred_formats:
        return resources
    for r in resources:
        if "_tags" not in r:
            enrich_resource(r)
    return sorted(
        resources,
        key=lambda r: score_resource(r, preferred_resolutions, preferred_formats),
        reverse=True,
    )
