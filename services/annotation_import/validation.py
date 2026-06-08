"""Validation helpers for annotation-derived review artifacts."""

from __future__ import annotations

from services.annotation_import.models import PaperEvidenceGraph, PathwayProposal, WarningRecord


def validate_evidence_graph(graph: PaperEvidenceGraph) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = []

    for edge in graph.edges:
        if edge.provenance.paper_id != graph.paper_id:
            warnings.append(
                WarningRecord(
                    code="edge_missing_paper_provenance",
                    message=f"Edge {edge.edge_id} has mismatched paper provenance.",
                    severity="error",
                    source_record_type=edge.source_record_type,
                    source_record_id=edge.source_record_id,
                )
            )
        if not edge.evidence_anchor_ids:
            warnings.append(
                WarningRecord(
                    code="mechanism_edge_missing_anchor",
                    message=f"Mechanism edge {edge.edge_id} has no evidence anchors.",
                    severity="error",
                    source_record_type=edge.source_record_type,
                    source_record_id=edge.source_record_id,
                )
            )
        if edge.source_record_type != "mechanism_step":
            warnings.append(
                WarningRecord(
                    code="mechanism_edge_non_top_level_source",
                    message=f"Mechanism edge {edge.edge_id} did not come from a top-level mechanism step.",
                    severity="error",
                    source_record_type=edge.source_record_type,
                    source_record_id=edge.source_record_id,
                )
            )

    for parameter in graph.parameters:
        if not parameter.source_record_id:
            warnings.append(
                WarningRecord(
                    code="parameter_missing_source_record",
                    message=f"Parameter {parameter.parameter_id} has no source record id.",
                    severity="error",
                    source_record_type=parameter.source_record_type,
                )
            )
        if parameter.unit is None and parameter.review_status != "review_only":
            warnings.append(
                WarningRecord(
                    code="parameter_missing_unit_not_review_only",
                    message=f"Parameter {parameter.parameter_id} is missing unit but is not review-only.",
                    severity="error",
                    source_record_type=parameter.source_record_type,
                    source_record_id=parameter.source_record_id,
                )
            )

    for simulation_parameter in graph.simulation_parameters:
        if not simulation_parameter.role:
            warnings.append(
                WarningRecord(
                    code="simulation_parameter_missing_role",
                    message=f"Simulation parameter {simulation_parameter.simulation_parameter_id} has no role.",
                    severity="error",
                    source_record_type="simulation_parameter",
                    source_record_id=simulation_parameter.simulation_parameter_id,
                )
            )
        if simulation_parameter.unit is None and simulation_parameter.review_status != "review_only":
            warnings.append(
                WarningRecord(
                    code="simulation_parameter_missing_unit_not_review_only",
                    message=(
                        f"Simulation parameter {simulation_parameter.simulation_parameter_id} "
                        "is missing unit but is not review-only."
                    ),
                    severity="error",
                    source_record_type="simulation_parameter",
                    source_record_id=simulation_parameter.simulation_parameter_id,
                )
            )

    for equation in graph.equations:
        if not equation.expression_text:
            warnings.append(
                WarningRecord(
                    code="equation_missing_expression",
                    message=f"Equation {equation.equation_id} has no expression text.",
                    severity="error",
                    source_record_type="equation",
                    source_record_id=equation.equation_id,
                )
            )
        if equation.metadata.get("executable") is not False:
            warnings.append(
                WarningRecord(
                    code="equation_not_display_only",
                    message=f"Equation {equation.equation_id} was not marked display-only.",
                    severity="error",
                    source_record_type="equation",
                    source_record_id=equation.equation_id,
                )
            )

    return tuple(warnings)


def assert_valid_evidence_graph(graph: PaperEvidenceGraph) -> None:
    warnings = validate_evidence_graph(graph)
    errors = tuple(warning for warning in warnings if warning.severity == "error")
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(messages)


def validate_pathway_proposal(proposal: PathwayProposal) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = []
    if proposal.executable:
        warnings.append(
            WarningRecord(
                code="proposal_claims_executable",
                message=f"Proposal {proposal.proposal_id} is marked executable.",
                severity="error",
            )
        )
    for edge in proposal.proposed_edges:
        if edge.source not in {node.node_id for node in proposal.proposed_nodes}:
            warnings.append(
                WarningRecord(
                    code="proposal_edge_missing_source_node",
                    message=f"Proposal edge {edge.edge_id} has missing source node {edge.source}.",
                    severity="error",
                    source_record_type="mechanism_step",
                    source_record_id=edge.source_evidence_id,
                )
            )
        if edge.target not in {node.node_id for node in proposal.proposed_nodes}:
            warnings.append(
                WarningRecord(
                    code="proposal_edge_missing_target_node",
                    message=f"Proposal edge {edge.edge_id} has missing target node {edge.target}.",
                    severity="error",
                    source_record_type="mechanism_step",
                    source_record_id=edge.source_evidence_id,
                )
            )
    return tuple(warnings)


def assert_valid_pathway_proposal(proposal: PathwayProposal) -> None:
    warnings = validate_pathway_proposal(proposal)
    errors = tuple(warning for warning in warnings if warning.severity == "error")
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(messages)
