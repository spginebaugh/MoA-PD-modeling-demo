"""Small deterministic claim-text helpers for toy MoA routing and ranking."""

from __future__ import annotations

import re

_CONTRAST_CUES = (
    re.compile(r"\brather\s+than\b", re.IGNORECASE),
    re.compile(r"\binstead\s+of\b", re.IGNORECASE),
    re.compile(r"\bas\s+opposed\s+to\b", re.IGNORECASE),
)
_NEGATED_SEGMENT_PATTERNS = (
    re.compile(r"\bbut\s+not\b[^,.;]*", re.IGNORECASE),
    re.compile(r"\bdoes\s+not\b[^,.;]*", re.IGNORECASE),
    re.compile(r"\bdo\s+not\b[^,.;]*", re.IGNORECASE),
    re.compile(r"\bnot\b[^,.;]*", re.IGNORECASE),
    re.compile(r"\bwithout\b[^,.;]*", re.IGNORECASE),
)


def _compact_text(value: str) -> str:
    return " ".join(value.replace(",", " ").replace(";", " ").split())


def _split_contrast(claim_text: str) -> tuple[str, str]:
    first_match: re.Match[str] | None = None
    for cue in _CONTRAST_CUES:
        match = cue.search(claim_text)
        if match is not None and (first_match is None or match.start() < first_match.start()):
            first_match = match
    if first_match is None:
        return claim_text, ""
    return claim_text[: first_match.start()], claim_text[first_match.end() :]


def _remove_negated_segments(claim_text: str) -> tuple[str, tuple[str, ...]]:
    negated: list[str] = []

    def replace(match: re.Match[str]) -> str:
        negated.append(match.group(0))
        return " "

    active = claim_text
    for pattern in _NEGATED_SEGMENT_PATTERNS:
        active = pattern.sub(replace, active)
    return active, tuple(_compact_text(item) for item in negated if _compact_text(item))


def active_claim_text_for_keywords(claim_text: str) -> str:
    """Return text that should contribute positive mechanism keywords."""

    positive_text, _ = _split_contrast(claim_text)
    active_text, _ = _remove_negated_segments(positive_text)
    return _compact_text(active_text)


def negated_claim_text_for_keywords(claim_text: str) -> str:
    """Return contrast/negated text that should not count as positive evidence."""

    positive_text, contrast_text = _split_contrast(claim_text)
    _, negated_segments = _remove_negated_segments(positive_text)
    ignored = (*negated_segments, _compact_text(contrast_text))
    return _compact_text(" ".join(item for item in ignored if item))
