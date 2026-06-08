"""Generate review-only pathway proposal artifacts from evidence graphs."""

from __future__ import annotations

import re

from services.annotation_import.models import (
    AnnotationProposalRule,
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
from services.annotation_import.rules import load_proposal_rule

_SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9_]+")


def build_pathway_proposal(
    graph: PaperEvidenceGraph,
    proposal_rule: AnnotationProposalRule | None = None,
) -> PathwayProposal:
    rule = proposal_rule if proposal_rule is not None else load_proposal_rule(graph.paper_id)
    proposal_kind = _proposal_kind(graph, rule)
    proposed_edges = tuple(_proposed_edges(graph))
    proposed_nodes = tuple(_proposed_nodes(graph, proposed_edges, proposal_kind, rule))
    proposed_parameters = tuple(_proposed_parameters(graph))
    proposed_equations = tuple(_proposed_equations(graph))
    missing_inputs = tuple(_missing_inputs(graph))

    return PathwayProposal(
        proposal_id=f"proposal:{graph.paper_id}:{proposal_kind}",
        paper_id=graph.paper_id,
        title=graph.title,
        proposal_kind=proposal_kind,
        target_pathway_id=_target_pathway_id(proposal_kind, rule),
        proposed_pathway_id=_proposed_pathway_id(graph, proposal_kind, rule),
        proposed_nodes=proposed_nodes,
        proposed_edges=proposed_edges,
        proposed_parameters=proposed_parameters,
        proposed_equations=proposed_equations,
        required_missing_inputs=missing_inputs,
        provenance_warnings=graph.warnings,
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
            )
        )
    return proposed


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
            )
        )
    if proposal_kind == "overlay" and not nodes and proposal_rule is not None:
        nodes.extend(_overlay_nodes_from_parameters(graph.simulation_parameters, proposal_rule.overlay_nodes))
    return nodes


def _overlay_nodes_from_parameters(
    simulation_parameters: tuple[EvidenceSimulationParameter, ...],
    overlay_rules: tuple[OverlayNodeRule, ...],
) -> list[ProposedNode]:
    nodes: list[ProposedNode] = []
    for overlay_rule in overlay_rules:
        source_ids = tuple(
            parameter.simulation_parameter_id
            for parameter in simulation_parameters
            if _matches_any_term(parameter.parameter_name, overlay_rule.match_terms)
        )
        if not source_ids:
            continue
        nodes.append(
            ProposedNode(
                node_id=overlay_rule.node_id,
                label=overlay_rule.label,
                node_type=overlay_rule.node_type,
                source_evidence_ids=source_ids[: overlay_rule.max_source_evidence_ids],
                review_status=overlay_rule.review_status,
                reason=overlay_rule.reason,
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
            )
        )
    return proposed


def _proposed_equations(graph: PaperEvidenceGraph) -> list[ProposedEquation]:
    return [
        ProposedEquation(
            equation_id=equation.equation_id,
            expression_text=equation.expression_text,
            source_evidence_id=equation.equation_id,
            review_status=equation.review_status,
            reason="Display/model-form equation; state and parameter bindings are not curated.",
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
