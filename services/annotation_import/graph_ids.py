"""Stable identifiers and labels for annotation evidence graph records."""

from __future__ import annotations

import hashlib
import json
import re

from services.annotation_import.models import ContextScope, EvidenceAnchor

_SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9_]+")


def slug(value: str) -> str:
    normalized = _SLUG_PATTERN.sub("_", value).strip("_").lower()
    return normalized[:80] or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def raw_node_id(paper_id: str, label: str) -> str:
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:10]
    return f"raw:{paper_id}:{slug(label)}:{digest}"


def context_node_id(paper_id: str, context: ContextScope) -> str:
    encoded = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:12]
    return f"context:{paper_id}:{digest}"


def quantity_node_id(paper_id: str, label: str) -> str:
    digest = hashlib.sha1(label.lower().encode("utf-8")).hexdigest()[:10]
    return f"model_quantity:{paper_id}:{slug(label)}:{digest}"


def link_id(paper_id: str, source: str, relation: str, target: str, source_record_id: str) -> str:
    raw = "|".join((paper_id, source, relation, target, source_record_id))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"link:{paper_id}:{slug(relation)}:{digest}"


def coalesce_anchor_ids(primary: tuple[str, ...], fallback: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*primary, *fallback)))


def anchor_label(anchor: EvidenceAnchor) -> str:
    location = anchor.cell_id or anchor.table_id or anchor.figure_id or anchor.chunk_id or anchor.anchor_id
    return f"{anchor.source_type or 'evidence'}:{location}"


def defined_equation_symbols(expression_text: str) -> frozenset[str]:
    lhs, separator, _rhs = expression_text.partition("=")
    if not separator:
        return frozenset()
    return frozenset(re.findall(r"[A-Za-z][A-Za-z0-9_]*", lhs))
