"""Claim text features loaded from pathway data."""

from __future__ import annotations

import re

from services.pathway.models import PredictionDefinition


def active_claim_text_for_keywords(claim_text: str) -> str:
    return re.split(r"\brather\s+than\b|\binstead\s+of\b|\bnot\b", claim_text, maxsplit=1, flags=re.I)[0]


def negated_claim_text(claim_text: str) -> str:
    parts = re.split(r"\brather\s+than\b|\binstead\s+of\b|\bnot\b", claim_text, maxsplit=1, flags=re.I)
    return parts[1] if len(parts) > 1 else ""


def claim_keywords_used(claim_text: str, prediction: PredictionDefinition) -> tuple[str, ...]:
    lower = active_claim_text_for_keywords(claim_text).lower()
    matched: list[str] = []
    for label, patterns in prediction.keyword_patterns.items():
        if any(pattern.lower() in lower for pattern in patterns):
            matched.append(label)
    return tuple(matched)


def negated_claim_keywords_used(claim_text: str, prediction: PredictionDefinition) -> tuple[str, ...]:
    lower = negated_claim_text(claim_text).lower()
    matched: list[str] = []
    for label, patterns in prediction.keyword_patterns.items():
        if any(pattern.lower() in lower for pattern in patterns):
            matched.append(label)
    return tuple(matched)


def matches_keywords(text: str, keywords: tuple[str, ...]) -> bool:
    lower = active_claim_text_for_keywords(text).lower()
    return all(keyword.lower() in lower for keyword in keywords)


def matches_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lower = active_claim_text_for_keywords(text).lower()
    return any(keyword.lower() in lower for keyword in keywords)
