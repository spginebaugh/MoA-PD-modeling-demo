"""Generate review-only pathway proposal artifacts from evidence graphs."""

from __future__ import annotations

import re

from services.annotation_import.curated_graph_builder import build_curated_paper_moa_graph
from services.annotation_import.models import (
    AnnotationProposalRule,
    CuratedPaperMoaGraph,
    EvidenceSimulationParameter,
    MissingInput,
    OverlayNodeRule,
    PaperEvidenceGraph,
    PathwayProposal,
    ProposalKind,
    ProposedEdge,
    ProposedEquation,
    ProposedNode,
    ProposedParameter,
    ReviewStatus,
)
from services.annotation_import.rules import load_curated_graph_rule, load_proposal_rule

_SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9_]+")


def build_pathway_proposal(
    graph: PaperEvidenceGraph,
    proposal_rule: AnnotationProposalRule | None = None,
) -> PathwayProposal:
    rule = proposal_rule if proposal_rule is not None else load_proposal_rule(graph.paper_id)
    curated_rule = load_curated_graph_rule(graph.paper_id) if proposal_rule is None else None
    curated_graph = build_curated_paper_moa_graph(graph, curated_rule) if curated_rule is not None else None
    proposal_kind = _proposal_kind(graph, rule)
    if curated_graph is not None:
        proposed_edges = tuple(_proposed_edges_from_curated_graph(curated_graph))
        proposed_nodes = tuple(_proposed_nodes_from_curated_graph(curated_graph))
        proposed_parameters = tuple(_proposed_parameters_from_curated_graph(curated_graph))
        proposed_equations = tuple(_proposed_equations_from_curated_graph(curated_graph))
        missing_inputs = curated_graph.missing_inputs
        provenance_warnings = curated_graph.warnings
    else:
        proposed_edges = tuple(_proposed_edges(graph))
        proposed_nodes = tuple(_proposed_nodes(graph, proposed_edges, proposal_kind, rule))
        proposed_parameters = tuple(_proposed_parameters(graph))
        proposed_equations = tuple(_proposed_equations(graph))
        missing_inputs = tuple(_missing_inputs(graph))
        provenance_warnings = graph.warnings

    return PathwayProposal(
        proposal_id=f"proposal:{graph.paper_id}:{proposal_kind}",
        paper_id=graph.paper_id,
        title=graph.title,
        curated_graph_id=curated_graph.graph_id if curated_graph is not None else None,
        proposal_kind=proposal_kind,
        target_pathway_id=_target_pathway_id(proposal_kind, rule),
        proposed_pathway_id=_proposed_pathway_id(graph, proposal_kind, rule),
        proposed_nodes=proposed_nodes,
        proposed_edges=proposed_edges,
        proposed_parameters=proposed_parameters,
        proposed_equations=proposed_equations,
        required_missing_inputs=missing_inputs,
        provenance_warnings=provenance_warnings,
        executable=False,
    )


def _proposal_kind(
    graph: PaperEvidenceGraph,
    proposal_rule: AnnotationProposalRule | None,
) -> ProposalKind:
    if proposal_rule is not None:
        return proposal_rule.proposal_kind
    if any(edge.review_status == "candidate_for_pathway_patch" for edge in graph.edges):
        return "new_pathway"
    return "evidence_only"


def _target_pathway_id(
    proposal_kind: ProposalKind,
    proposal_rule: AnnotationProposalRule | None,
) -> str | None:
    if proposal_kind != "overlay" or proposal_rule is None:
        return None
    return proposal_rule.target_pathway_id


def _proposed_pathway_id(
    graph: PaperEvidenceGraph,
    proposal_kind: ProposalKind,
    proposal_rule: AnnotationProposalRule | None,
) -> str | None:
    if proposal_kind != "new_pathway":
        return None
    if proposal_rule is not None and proposal_rule.proposed_pathway_id:
        return proposal_rule.proposed_pathway_id
    return f"{_slug(graph.paper_id)}_paper_moa_demo"


def _proposed_edges(graph: PaperEvidenceGraph) -> list[ProposedEdge]:
    proposed: list[ProposedEdge] = []
    for edge in graph.edges:
        if edge.review_status != "candidate_for_pathway_patch":
            continue
        proposed.append(
            ProposedEdge(
                edge_id=edge.edge_id,
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
                source_evidence_id=edge.source_record_id,
                verification_verdict=edge.verification_verdict,
                review_status=edge.review_status,
                reason=_edge_reason(edge.verification_verdict),
                evidence_anchor_ids=edge.evidence_anchor_ids,
                context=edge.context,
                provenance=edge.provenance,
                warnings=edge.warnings,
                metadata=edge.metadata,
            )
        )
    return proposed


def _proposed_edges_from_curated_graph(graph: CuratedPaperMoaGraph) -> list[ProposedEdge]:
    return [
        ProposedEdge(
            edge_id=edge.edge_id,
            source=edge.source,
            target=edge.target,
            relation=edge.relation,
            source_evidence_id=edge.source_record_ids[0] if edge.source_record_ids else edge.edge_id,
            verification_verdict=None,
            review_status=edge.review_status,
            reason=edge.reason,
            evidence_anchor_ids=edge.evidence_anchor_ids,
            context=edge.context,
            provenance=edge.provenance[0] if edge.provenance else None,
            warnings=edge.warnings,
            metadata={
                **edge.metadata,
                "curated_graph_id": graph.graph_id,
                "causal_role": edge.causal_role,
                "support_level": edge.support_level,
                "source_record_ids": list(edge.source_record_ids),
                "supporting_mechanism_step_ids": list(edge.supporting_mechanism_step_ids),
                "supporting_parameter_ids": list(edge.supporting_parameter_ids),
                "supporting_equation_ids": list(edge.supporting_equation_ids),
            },
        )
        for edge in graph.edges
    ]


def _proposed_nodes(
    graph: PaperEvidenceGraph,
    proposed_edges: tuple[ProposedEdge, ...],
    proposal_kind: ProposalKind,
    proposal_rule: AnnotationProposalRule | None,
) -> list[ProposedNode]:
    proposed_node_ids = {edge.source for edge in proposed_edges} | {edge.target for edge in proposed_edges}
    nodes: list[ProposedNode] = []
    for node in graph.nodes:
        if node.node_id not in proposed_node_ids:
            continue
        nodes.append(
            ProposedNode(
                node_id=node.node_id,
                label=node.label,
                node_type=node.node_type,
                source_evidence_ids=(node.source_record_id,),
                review_status=node.review_status,
                reason="Node participates in a candidate pathway-patch mechanism edge.",
                evidence_anchor_ids=node.evidence_anchor_ids,
                context=node.context,
                provenance=node.provenance,
                metadata=node.metadata,
            )
        )
    if proposal_kind == "overlay" and not nodes and proposal_rule is not None:
        nodes.extend(_overlay_nodes_from_parameters(graph.simulation_parameters, proposal_rule.overlay_nodes))
    return nodes


def _proposed_nodes_from_curated_graph(graph: CuratedPaperMoaGraph) -> list[ProposedNode]:
    return [
        ProposedNode(
            node_id=node.node_id,
            label=node.label,
            node_type=node.node_type,
            source_evidence_ids=node.source_record_ids,
            review_status=node.review_status,
            reason=node.reason,
            evidence_anchor_ids=node.evidence_anchor_ids,
            context=node.context,
            provenance=node.provenance[0] if node.provenance else None,
            warnings=node.warnings,
            metadata={**node.metadata, "curated_graph_id": graph.graph_id},
        )
        for node in graph.nodes
    ]


def _overlay_nodes_from_parameters(
    simulation_parameters: tuple[EvidenceSimulationParameter, ...],
    overlay_rules: tuple[OverlayNodeRule, ...],
) -> list[ProposedNode]:
    nodes: list[ProposedNode] = []
    for overlay_rule in overlay_rules:
        matched_parameters = tuple(
            parameter
            for parameter in simulation_parameters
            if _matches_any_term(parameter.parameter_name, overlay_rule.match_terms)
        )
        source_ids = tuple(parameter.simulation_parameter_id for parameter in matched_parameters)
        if not source_ids:
            continue
        first_parameter = matched_parameters[0]
        nodes.append(
            ProposedNode(
                node_id=overlay_rule.node_id,
                label=overlay_rule.label,
                node_type=overlay_rule.node_type,
                source_evidence_ids=source_ids[: overlay_rule.max_source_evidence_ids],
                review_status=overlay_rule.review_status,
                reason=overlay_rule.reason,
                evidence_anchor_ids=_coalesce_anchor_ids(
                    *(parameter.evidence_anchor_ids for parameter in matched_parameters)
                ),
                context=first_parameter.context,
                provenance=first_parameter.provenance,
                warnings=tuple(
                    dict.fromkeys(
                        warning for parameter in matched_parameters for warning in parameter.warnings
                    )
                ),
                metadata={
                    "matched_source_count": len(matched_parameters),
                    "match_terms": list(overlay_rule.match_terms),
                },
            )
        )
    return nodes


def _proposed_parameters(graph: PaperEvidenceGraph) -> list[ProposedParameter]:
    proposed: list[ProposedParameter] = []
    for simulation_parameter in graph.simulation_parameters:
        proposed.append(
            ProposedParameter(
                parameter_id=simulation_parameter.simulation_parameter_id,
                name=simulation_parameter.parameter_name,
                role=simulation_parameter.role,
                source_evidence_id=simulation_parameter.simulation_parameter_id,
                value=simulation_parameter.value,
                unit=simulation_parameter.unit,
                review_status=simulation_parameter.review_status,
                reason=_parameter_reason(simulation_parameter.review_status, simulation_parameter.role),
                evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
                context=simulation_parameter.context,
                provenance=simulation_parameter.provenance,
                warnings=simulation_parameter.warnings,
                metadata=simulation_parameter.metadata,
            )
        )
    for parameter in graph.parameters:
        proposed.append(
            ProposedParameter(
                parameter_id=parameter.parameter_id,
                name=parameter.name,
                role=parameter.family or "parameter",
                source_evidence_id=parameter.source_record_id,
                value=parameter.value,
                unit=parameter.unit,
                review_status=parameter.review_status,
                reason=_parameter_reason(parameter.review_status, parameter.family or "parameter"),
                evidence_anchor_ids=parameter.evidence_anchor_ids,
                context=parameter.context,
                provenance=parameter.provenance,
                warnings=parameter.warnings,
                metadata=parameter.metadata,
            )
        )
    return proposed


def _proposed_parameters_from_curated_graph(graph: CuratedPaperMoaGraph) -> list[ProposedParameter]:
    return [
        ProposedParameter(
            parameter_id=parameter.parameter_id,
            name=parameter.name,
            role=parameter.role,
            source_evidence_id=parameter.source_record_ids[0]
            if parameter.source_record_ids
            else parameter.parameter_id,
            value=parameter.value,
            unit=parameter.unit,
            review_status=parameter.review_status,
            reason=parameter.reason,
            evidence_anchor_ids=parameter.evidence_anchor_ids,
            context=parameter.context,
            provenance=parameter.provenance[0] if parameter.provenance else None,
            warnings=(*parameter.promotion_blockers, *parameter.warnings),
            metadata={
                **parameter.metadata,
                "curated_graph_id": graph.graph_id,
                "symbol": parameter.symbol,
                "target_node_id": parameter.target_node_id,
                "target_edge_id": parameter.target_edge_id,
                "source_record_ids": list(parameter.source_record_ids),
                "promotion_blockers": list(parameter.promotion_blockers),
            },
        )
        for parameter in graph.parameters
    ]


def _proposed_equations(graph: PaperEvidenceGraph) -> list[ProposedEquation]:
    return [
        ProposedEquation(
            equation_id=equation.equation_id,
            expression_text=equation.expression_text,
            source_evidence_id=equation.equation_id,
            review_status=equation.review_status,
            reason="Display/model-form equation; state and parameter bindings are not curated.",
            evidence_anchor_ids=equation.evidence_anchor_ids,
            context=equation.context,
            provenance=equation.provenance,
            metadata=equation.metadata,
        )
        for equation in graph.equations
    ]


def _proposed_equations_from_curated_graph(graph: CuratedPaperMoaGraph) -> list[ProposedEquation]:
    return [
        ProposedEquation(
            equation_id=equation.equation_id,
            expression_text=equation.expression_text,
            source_evidence_id=equation.source_record_ids[0]
            if equation.source_record_ids
            else equation.equation_id,
            review_status=equation.review_status,
            reason=equation.reason,
            evidence_anchor_ids=equation.evidence_anchor_ids,
            context=equation.context,
            provenance=equation.provenance[0] if equation.provenance else None,
            metadata={
                **equation.metadata,
                "curated_graph_id": graph.graph_id,
                "binding_type": equation.binding_type,
                "target_node_id": equation.target_node_id,
                "target_edge_id": equation.target_edge_id,
                "model_form": equation.model_form,
                "source_record_ids": list(equation.source_record_ids),
                "display_only": True,
                "executable": False,
            },
        )
        for equation in graph.equations
    ]


def _missing_inputs(graph: PaperEvidenceGraph) -> list[MissingInput]:
    missing: list[MissingInput] = []
    for warning in graph.warnings:
        if warning.code != "missing_model_input":
            continue
        message = warning.message
        name, _, reason = message.partition(":")
        missing.append(
            MissingInput(
                name=name.replace("Missing ", "", 1),
                reason=reason.strip() or message,
                severity=warning.severity,
            )
        )
    return missing


def _edge_reason(verdict: str | None) -> str:
    if verdict == "verified_therapeutic_moa":
        return "Verified therapeutic MOA in top-level mechanism verification."
    if verdict == "model_derived_pd_relation":
        return "Model-derived PD relation; candidate only after model-binding review."
    return "Not promoted automatically; review required."


def _parameter_reason(review_status: ReviewStatus, role: str) -> str:
    if review_status == "candidate_for_pathway_patch":
        return f"{role} record has sufficient extracted support for proposal review."
    if role == "calibration_or_validation_endpoint":
        return "Calibration or validation endpoint; use for review, not as a direct parameter prior."
    return "Review required before executable parameter promotion."


def _slug(value: str) -> str:
    return _SLUG_PATTERN.sub("_", value).strip("_").lower()


def _matches_any_term(value: str, terms: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(term.lower() in lowered for term in terms)


def _coalesce_anchor_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(anchor_id for group in groups for anchor_id in group))
