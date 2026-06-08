"""Provenance and conservative context extraction for annotation records."""

from __future__ import annotations

import re
from collections.abc import Iterable

from services.annotation_import.models import (
    ContextExtractionRules,
    ContextScope,
    EvidenceAnchor,
    JsonDict,
    PaperInfo,
    PaperProvenance,
    SourceRecordType,
    TermRule,
)
from services.annotation_import.rules import load_context_rules
from services.domain.base import JsonValue


def anchor_index(anchors: Iterable[EvidenceAnchor]) -> dict[str, EvidenceAnchor]:
    return {anchor.anchor_id: anchor for anchor in anchors}


def context_scope(
    context: JsonDict,
    evidence_anchor_ids: tuple[str, ...],
    anchors: dict[str, EvidenceAnchor],
    text: str | None = None,
    rules: ContextExtractionRules | None = None,
) -> ContextScope:
    anchor_text = " ".join(
        part for anchor_id in evidence_anchor_ids for part in _anchor_text_parts(anchors.get(anchor_id))
    )
    context_text = " ".join(_context_text_parts(context))
    combined_text = " ".join(part for part in (text, anchor_text, context_text) if part)
    lowered = combined_text.lower()
    context_rules = rules or load_context_rules()

    species = _first_context_value(context, ("species",)) or _first_rule_match(lowered, context_rules.species)
    translation_stage = _first_context_value(context, ("translation_stage", "study_context_type"))
    if translation_stage is None and species == "human" and _rule_value_matches(
        lowered, context_rules.translation_stage, "clinical"
    ):
        translation_stage = "clinical"
    translation_stage = translation_stage or _first_rule_match(lowered, context_rules.translation_stage)
    model_system = _first_context_value(context, ("model_system", "study_context_type"))
    if model_system is None and species == "human" and translation_stage == "clinical":
        model_system = "clinical"
    model_system = model_system or _first_rule_match(lowered, context_rules.model_system) or translation_stage
    return ContextScope(
        species=species,
        translation_stage=translation_stage,
        disease=_first_rule_match(lowered, context_rules.disease),
        disease_subtype=_first_rule_match(lowered, context_rules.disease_subtype),
        state=_all_rule_matches(lowered, context_rules.state),
        assay=_first_context_value(context, ("assay_contexts", "assay_context")),
        matrix=_first_context_value(context, ("matrix_contexts", "matrix_context")),
        tissue_or_organ=_first_context_value(context, ("organ_contexts", "organ_context")),
        cell_line=_first_context_value(context, ("cell_line_contexts", "cell_line")),
        model_system=model_system,
        drug_or_analyte=_first_context_value(
            context,
            ("drug_contexts", "drug_context", "drug_or_analyte", "analytes"),
        ),
        source_section=_source_section(evidence_anchor_ids, anchors, context),
        source_anchor_ids=evidence_anchor_ids,
    )


def paper_provenance(
    paper: PaperInfo,
    source_record_type: SourceRecordType,
    source_record_id: str,
    evidence_anchor_ids: tuple[str, ...],
    anchors: dict[str, EvidenceAnchor],
    quote_or_sentence: str | None = None,
    simulation_model_id: str | None = None,
    simulation_parameter_id: str | None = None,
    verification_id: str | None = None,
    verification_verdict: str | None = None,
    relation_class: str | None = None,
    validation_status: str | None = None,
    trust_level: str | None = None,
    warnings: tuple[str, ...] = (),
) -> PaperProvenance:
    first_anchor = _first_anchor(evidence_anchor_ids, anchors)
    return PaperProvenance(
        paper_id=paper.paper_id,
        paper_title=paper.title,
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        evidence_anchor_ids=evidence_anchor_ids,
        source_section=first_anchor.section if first_anchor else None,
        source_chunk_id=first_anchor.chunk_id if first_anchor else None,
        source_table_or_figure=_table_or_figure(first_anchor),
        quote_or_sentence=quote_or_sentence or (first_anchor.quote if first_anchor else None),
        simulation_model_id=simulation_model_id,
        simulation_parameter_id=simulation_parameter_id,
        verification_id=verification_id,
        verification_verdict=verification_verdict,
        relation_class=relation_class,
        validation_status=validation_status,
        trust_level=trust_level,
        warnings=warnings,
    )


def missing_inputs_from_context(context: JsonDict) -> tuple[str, ...]:
    missing = context.get("missing_inputs")
    if not isinstance(missing, list):
        return ()
    names: list[str] = []
    for item in missing:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                names.append(name)
    return tuple(names)


def _first_anchor(
    evidence_anchor_ids: tuple[str, ...],
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceAnchor | None:
    for anchor_id in evidence_anchor_ids:
        anchor = anchors.get(anchor_id)
        if anchor is not None:
            return anchor
    return None


def _anchor_text_parts(anchor: EvidenceAnchor | None) -> tuple[str, ...]:
    if anchor is None:
        return ()
    return tuple(
        part
        for part in (
            anchor.quote,
            anchor.section,
            anchor.table_id,
            anchor.figure_id,
            anchor.row_header,
            anchor.column_header,
            anchor.panel_id,
        )
        if part
    )


def _context_text_parts(context: JsonDict) -> tuple[str, ...]:
    parts: list[str] = []
    for key in (
        "section",
        "sentence",
        "figure_label",
        "figure_id",
        "panel_id",
        "table_id",
        "row_header",
        "column_header",
        "parameter_name",
        "parameter",
        "caption",
        "species",
        "study_context_type",
    ):
        value = context.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in (
        "drug_contexts",
        "assay_contexts",
        "matrix_contexts",
        "organ_contexts",
        "cell_line_contexts",
        "pd_targets",
        "compartments",
        "analytes",
        "disease_contexts",
        "mutation_contexts",
        "exposure_durations",
        "visual_evidence_types",
    ):
        value = context.get(key)
        if isinstance(value, list):
            parts.extend(item for item in value if isinstance(item, str))
    return tuple(parts)


def _first_context_value(context: JsonDict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = context.get(key)
        flattened = _flatten_context_value(value)
        if flattened:
            return flattened
        pd_context = context.get("pd_context")
        if isinstance(pd_context, dict):
            flattened = _flatten_context_value(pd_context.get(key))
            if flattened:
                return flattened
        study_context = context.get("study_context")
        if isinstance(study_context, dict):
            flattened = _flatten_context_value(study_context.get(key))
            if flattened:
                return flattened
    return None


def _flatten_context_value(value: JsonValue | None) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, list):
        strings = tuple(item for item in value if isinstance(item, str) and item)
        if strings:
            return ", ".join(strings)
    return None


def _source_section(
    evidence_anchor_ids: tuple[str, ...],
    anchors: dict[str, EvidenceAnchor],
    context: JsonDict,
) -> str | None:
    first_anchor = _first_anchor(evidence_anchor_ids, anchors)
    if first_anchor and first_anchor.section:
        return first_anchor.section
    section = context.get("section")
    return section if isinstance(section, str) else None


def _table_or_figure(anchor: EvidenceAnchor | None) -> str | None:
    if anchor is None:
        return None
    if anchor.table_id:
        return anchor.table_id
    if anchor.figure_id:
        return anchor.figure_id
    return None


def _first_rule_match(text: str, rules: tuple[TermRule, ...]) -> str | None:
    for rule in rules:
        if _matches_any_term(text, rule.terms):
            return rule.value
    return None


def _all_rule_matches(text: str, rules: tuple[TermRule, ...]) -> str | None:
    matches = tuple(rule.value for rule in rules if _matches_any_term(text, rule.terms))
    return ", ".join(dict.fromkeys(matches)) or None


def _rule_value_matches(text: str, rules: tuple[TermRule, ...], value: str) -> bool:
    return any(rule.value == value and _matches_any_term(text, rule.terms) for rule in rules)


def _matches_any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(_matches_term(text, term) for term in terms)


def _matches_term(text: str, term: str) -> bool:
    normalized = term.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized)
    if normalized.isalpha() and not normalized.endswith("s"):
        escaped = f"{escaped}s?"
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None
