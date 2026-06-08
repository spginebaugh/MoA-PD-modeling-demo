"""Build curated non-executable MOA graph projections from evidence graphs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from services.annotation_import.models import (
    ContextScope,
    CuratedEdgeRule,
    CuratedEquationRule,
    CuratedGraphRule,
    CuratedGraphWarningRule,
    CuratedNodeRule,
    CuratedPaperMoaEdge,
    CuratedPaperMoaEquation,
    CuratedPaperMoaGraph,
    CuratedPaperMoaNode,
    CuratedPaperMoaParameter,
    CuratedParameterRule,
    EvidenceAnchor,
    EvidenceEquation,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    EvidenceParameter,
    EvidenceSimulationModel,
    EvidenceSimulationParameter,
    PaperEvidenceGraph,
    PaperInfo,
    PaperProvenance,
    WarningRecord,
)
from services.annotation_import.provenance import paper_provenance
from services.annotation_import.rules import load_curated_graph_rule
from services.domain.base import JsonValue


@dataclass
class _EvidenceRecord:
    source_record_id: str
    evidence_anchor_ids: tuple[str, ...]
    context: ContextScope
    provenance: tuple[PaperProvenance, ...]
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass
class _EvidenceIndex:
    records: dict[str, _EvidenceRecord]
    anchors: dict[str, EvidenceAnchor]
    warnings: list[WarningRecord]


def build_curated_paper_moa_graph(
    graph: PaperEvidenceGraph,
    curated_rule: CuratedGraphRule | None = None,
) -> CuratedPaperMoaGraph:
    rule = curated_rule if curated_rule is not None else load_curated_graph_rule(graph.paper_id)
    if rule is None:
        rule = CuratedGraphRule(
            paper_id=graph.paper_id,
            graph_id=f"curated:{graph.paper_id}:evidence_only",
            graph_kind="evidence_only",
            title=graph.title,
            warnings=(
                CuratedGraphWarningRule(
                    code="missing_curated_graph_rule",
                    message="No curated graph rule is available; returning an evidence-only curated shell.",
                ),
            ),
        )
    if rule.paper_id != graph.paper_id:
        raise ValueError(f"Curated graph rule for {rule.paper_id!r} cannot build graph {graph.paper_id!r}")

    index = _build_evidence_index(graph)
    nodes = tuple(_build_node(rule_node, index) for rule_node in rule.nodes)
    edges = tuple(_build_edge(rule_edge, index) for rule_edge in rule.edges)
    parameters = tuple(_build_parameter(rule_parameter, index) for rule_parameter in rule.parameters)
    equations = tuple(_build_equation(rule_equation, index) for rule_equation in rule.equations)
    contexts = _unique_contexts(
        *(node.context for node in nodes),
        *(edge.context for edge in edges),
        *(parameter.context for parameter in parameters),
        *(equation.context for equation in equations),
    )
    evidence_anchor_ids = _coalesce_ids(
        *(item.evidence_anchor_ids for item in (*nodes, *edges, *parameters, *equations))
    )
    evidence_anchors = tuple(
        anchor for anchor in graph.evidence_anchors if anchor.anchor_id in set(evidence_anchor_ids)
    )
    rule_warnings = tuple(
        WarningRecord(
            code=warning.code,
            message=warning.message,
            severity=warning.severity,
            source_record_type=warning.source_record_type,
            source_record_id=warning.source_record_id,
        )
        for warning in rule.warnings
    )
    warnings = (*graph.warnings, *rule_warnings, *index.warnings)

    return CuratedPaperMoaGraph(
        graph_id=rule.graph_id,
        paper_id=graph.paper_id,
        title=rule.title or graph.title,
        graph_kind=rule.graph_kind,
        nodes=nodes,
        edges=edges,
        parameters=parameters,
        equations=equations,
        contexts=contexts,
        evidence_anchors=evidence_anchors,
        missing_inputs=rule.missing_inputs,
        warnings=warnings,
        executable=False,
        summary={
            "node_count": len(nodes),
            "edge_count": len(edges),
            "parameter_count": len(parameters),
            "equation_count": len(equations),
            "context_count": len(contexts),
            "evidence_anchor_count": len(evidence_anchors),
            "warning_count": len(warnings),
            "review_status_counts": _review_status_counts(nodes, edges, parameters, equations),
            "runtime_executable": False,
            **rule.metadata,
        },
    )


def _build_evidence_index(graph: PaperEvidenceGraph) -> _EvidenceIndex:
    records: dict[str, _EvidenceRecord] = {}
    anchors = {anchor.anchor_id: anchor for anchor in graph.evidence_anchors}
    warnings: list[WarningRecord] = []

    for anchor in graph.evidence_anchors:
        provenance = paper_provenance(
            _paper_info(graph),
            "evidence_anchor",
            anchor.anchor_id,
            (anchor.anchor_id,),
            anchors,
            quote_or_sentence=anchor.quote,
            validation_status=anchor.source_type,
        )
        _add_record(
            records,
            anchor.anchor_id,
            _EvidenceRecord(
                source_record_id=anchor.anchor_id,
                evidence_anchor_ids=(anchor.anchor_id,),
                context=ContextScope(source_section=anchor.section, source_anchor_ids=(anchor.anchor_id,)),
                provenance=(provenance,),
                metadata={"source_type": anchor.source_type},
            ),
        )

    for node in graph.nodes:
        _add_record(records, node.node_id, _record_from_node(node))
        _add_record(records, node.source_record_id, _record_from_node(node))
    for edge in graph.edges:
        _add_record(records, edge.edge_id, _record_from_edge(edge))
        _add_record(records, edge.source_record_id, _record_from_edge(edge))
    for parameter in graph.parameters:
        _add_record(records, parameter.parameter_id, _record_from_parameter(parameter))
        _add_record(records, parameter.source_record_id, _record_from_parameter(parameter))
    for equation in graph.equations:
        _add_record(records, equation.equation_id, _record_from_equation(equation))
    for model in graph.simulation_models:
        _add_record(records, model.simulation_model_id, _record_from_simulation_model(model))
    for parameter in graph.simulation_parameters:
        _add_record(records, parameter.simulation_parameter_id, _record_from_simulation_parameter(parameter))

    return _EvidenceIndex(records=records, anchors=anchors, warnings=warnings)


def _build_node(rule: CuratedNodeRule, index: _EvidenceIndex) -> CuratedPaperMoaNode:
    source_ids = tuple(rule.source_record_ids)
    evidence = _resolve_sources(source_ids, index)
    anchor_ids = _coalesce_ids(rule.evidence_anchor_ids, evidence.evidence_anchor_ids)
    context = _merge_context(evidence.context, rule.context, anchor_ids)
    return CuratedPaperMoaNode(
        node_id=rule.node_id,
        label=rule.label,
        node_type=rule.node_type,
        source_record_ids=source_ids,
        review_status=rule.review_status,
        reason=rule.reason,
        evidence_anchor_ids=anchor_ids,
        context=context,
        provenance=evidence.provenance,
        warnings=rule.warnings,
        metadata=rule.metadata,
    )


def _build_edge(rule: CuratedEdgeRule, index: _EvidenceIndex) -> CuratedPaperMoaEdge:
    source_ids = _coalesce_ids(
        rule.source_record_ids,
        rule.supporting_mechanism_step_ids,
        rule.supporting_parameter_ids,
        rule.supporting_equation_ids,
    )
    evidence = _resolve_sources(source_ids, index)
    anchor_ids = _coalesce_ids(rule.evidence_anchor_ids, evidence.evidence_anchor_ids)
    context = _merge_context(evidence.context, rule.context, anchor_ids)
    return CuratedPaperMoaEdge(
        edge_id=rule.edge_id,
        source=rule.source,
        target=rule.target,
        relation=rule.relation,
        causal_role=rule.causal_role,
        support_level=rule.support_level,
        source_record_ids=source_ids,
        supporting_mechanism_step_ids=rule.supporting_mechanism_step_ids,
        supporting_parameter_ids=rule.supporting_parameter_ids,
        supporting_equation_ids=rule.supporting_equation_ids,
        review_status=rule.review_status,
        reason=rule.reason,
        evidence_anchor_ids=anchor_ids,
        context=context,
        provenance=evidence.provenance,
        warnings=rule.warnings,
        metadata=rule.metadata,
    )


def _build_parameter(rule: CuratedParameterRule, index: _EvidenceIndex) -> CuratedPaperMoaParameter:
    source_ids = tuple(rule.source_record_ids)
    evidence = _resolve_sources(source_ids, index)
    anchor_ids = _coalesce_ids(rule.evidence_anchor_ids, evidence.evidence_anchor_ids)
    context = _merge_context(evidence.context, rule.context, anchor_ids)
    return CuratedPaperMoaParameter(
        parameter_id=rule.parameter_id,
        name=rule.name,
        role=rule.role,
        source_record_ids=source_ids,
        symbol=rule.symbol,
        value=rule.value,
        unit=rule.unit,
        target_node_id=rule.target_node_id,
        target_edge_id=rule.target_edge_id,
        review_status=rule.review_status,
        reason=rule.reason,
        promotion_blockers=rule.promotion_blockers,
        evidence_anchor_ids=anchor_ids,
        context=context,
        provenance=evidence.provenance,
        warnings=rule.warnings,
        metadata=rule.metadata,
    )


def _build_equation(rule: CuratedEquationRule, index: _EvidenceIndex) -> CuratedPaperMoaEquation:
    source_ids = tuple(rule.source_record_ids)
    evidence = _resolve_sources(source_ids, index)
    anchor_ids = _coalesce_ids(rule.evidence_anchor_ids, evidence.evidence_anchor_ids)
    context = _merge_context(evidence.context, rule.context, anchor_ids)
    return CuratedPaperMoaEquation(
        equation_id=rule.equation_id,
        expression_text=rule.expression_text,
        binding_type=rule.binding_type,
        source_record_ids=source_ids,
        target_node_id=rule.target_node_id,
        target_edge_id=rule.target_edge_id,
        model_form=rule.model_form,
        review_status=rule.review_status,
        reason=rule.reason,
        evidence_anchor_ids=anchor_ids,
        context=context,
        provenance=evidence.provenance,
        warnings=rule.warnings,
        metadata=rule.metadata,
    )


@dataclass(frozen=True)
class _ResolvedEvidence:
    evidence_anchor_ids: tuple[str, ...]
    context: ContextScope
    provenance: tuple[PaperProvenance, ...]


def _resolve_sources(source_ids: tuple[str, ...], index: _EvidenceIndex) -> _ResolvedEvidence:
    records: list[_EvidenceRecord] = []
    for source_id in source_ids:
        record = index.records.get(source_id)
        if record is None:
            index.warnings.append(
                WarningRecord(
                    code="curated_source_record_missing",
                    message=f"Curated graph source record {source_id!r} was not found in the evidence graph.",
                    source_record_id=source_id,
                )
            )
            continue
        records.append(record)

    return _ResolvedEvidence(
        evidence_anchor_ids=_coalesce_ids(*(record.evidence_anchor_ids for record in records)),
        context=_first_signaled_context(records),
        provenance=_coalesce_provenance(*(record.provenance for record in records)),
    )


def _record_from_node(node: EvidenceGraphNode) -> _EvidenceRecord:
    return _EvidenceRecord(
        source_record_id=node.source_record_id,
        evidence_anchor_ids=node.evidence_anchor_ids,
        context=node.context,
        provenance=(node.provenance,),
        metadata=node.metadata,
    )


def _record_from_edge(edge: EvidenceGraphEdge) -> _EvidenceRecord:
    return _EvidenceRecord(
        source_record_id=edge.source_record_id,
        evidence_anchor_ids=edge.evidence_anchor_ids,
        context=edge.context,
        provenance=(edge.provenance,),
        metadata=edge.metadata,
    )


def _record_from_parameter(parameter: EvidenceParameter) -> _EvidenceRecord:
    return _EvidenceRecord(
        source_record_id=parameter.source_record_id,
        evidence_anchor_ids=parameter.evidence_anchor_ids,
        context=parameter.context,
        provenance=(parameter.provenance,),
        metadata=parameter.metadata,
    )


def _record_from_equation(equation: EvidenceEquation) -> _EvidenceRecord:
    return _EvidenceRecord(
        source_record_id=equation.equation_id,
        evidence_anchor_ids=equation.evidence_anchor_ids,
        context=equation.context,
        provenance=(equation.provenance,),
        metadata=equation.metadata,
    )


def _record_from_simulation_model(model: EvidenceSimulationModel) -> _EvidenceRecord:
    return _EvidenceRecord(
        source_record_id=model.simulation_model_id,
        evidence_anchor_ids=model.evidence_anchor_ids,
        context=model.context,
        provenance=(model.provenance,),
        metadata=model.metadata,
    )


def _record_from_simulation_parameter(parameter: EvidenceSimulationParameter) -> _EvidenceRecord:
    return _EvidenceRecord(
        source_record_id=parameter.simulation_parameter_id,
        evidence_anchor_ids=parameter.evidence_anchor_ids,
        context=parameter.context,
        provenance=(parameter.provenance,),
        metadata=parameter.metadata,
    )


def _add_record(records: dict[str, _EvidenceRecord], key: str, record: _EvidenceRecord) -> None:
    records.setdefault(key, record)


def _paper_info(graph: PaperEvidenceGraph) -> PaperInfo:
    return PaperInfo(paper_id=graph.paper_id, title=graph.title, source=graph.source)


def _first_signaled_context(records: list[_EvidenceRecord]) -> ContextScope:
    for record in records:
        if _context_has_signal(record.context):
            return record.context
    return records[0].context if records else ContextScope()


def _merge_context(
    base: ContextScope, override: ContextScope, evidence_anchor_ids: tuple[str, ...]
) -> ContextScope:
    payload = base.model_dump(mode="json")
    override_payload = override.model_dump(mode="json")
    for key, value in override_payload.items():
        if value not in (None, "", ()):
            payload[key] = value
    if not payload.get("source_anchor_ids"):
        payload["source_anchor_ids"] = evidence_anchor_ids
    return ContextScope.model_validate(payload)


def _context_has_signal(context: ContextScope) -> bool:
    payload = context.model_dump(mode="json")
    return any(
        value
        for key, value in payload.items()
        if key not in {"source_anchor_ids", "source_section"} and value is not None
    )


def _unique_contexts(*contexts: ContextScope) -> tuple[ContextScope, ...]:
    unique: dict[str, ContextScope] = {}
    for context in contexts:
        if not _context_has_signal(context):
            continue
        encoded = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        unique.setdefault(encoded, context)
    return tuple(unique.values())


def _coalesce_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group if item))


def _coalesce_provenance(*groups: tuple[PaperProvenance, ...]) -> tuple[PaperProvenance, ...]:
    records: dict[tuple[str, str], PaperProvenance] = {}
    for group in groups:
        for provenance in group:
            records.setdefault((provenance.source_record_type, provenance.source_record_id), provenance)
    return tuple(records.values())


def _review_status_counts(
    nodes: tuple[CuratedPaperMoaNode, ...],
    edges: tuple[CuratedPaperMoaEdge, ...],
    parameters: tuple[CuratedPaperMoaParameter, ...],
    equations: tuple[CuratedPaperMoaEquation, ...],
) -> dict[str, JsonValue]:
    counts: dict[str, JsonValue] = {}
    for bucket, items in (
        ("nodes", nodes),
        ("edges", edges),
        ("parameters", parameters),
        ("equations", equations),
    ):
        bucket_counts: dict[str, JsonValue] = {}
        for item in items:
            status = item.review_status
            current = bucket_counts.get(status, 0)
            bucket_counts[status] = current + 1 if isinstance(current, int) else 1
        counts[bucket] = bucket_counts
    return counts
