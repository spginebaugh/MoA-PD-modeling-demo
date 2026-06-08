"""Validation helpers for annotation-derived review artifacts."""

from __future__ import annotations

from services.annotation_import.models import (
    CuratedPaperMoaGraph,
    PaperEvidenceGraph,
    PathwayProposal,
    WarningRecord,
)


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

    node_ids = {node.node_id for node in graph.nodes}
    for link in graph.links:
        if link.provenance.paper_id != graph.paper_id:
            warnings.append(
                WarningRecord(
                    code="link_missing_paper_provenance",
                    message=f"Link {link.link_id} has mismatched paper provenance.",
                    severity="error",
                    source_record_type=link.source_record_type,
                    source_record_id=link.source_record_id,
                )
            )
        if not link.relation:
            warnings.append(
                WarningRecord(
                    code="link_missing_relation",
                    message=f"Link {link.link_id} has no relation.",
                    severity="error",
                    source_record_type=link.source_record_type,
                    source_record_id=link.source_record_id,
                )
            )
        if link.relation not in {
            "unresolved_observation_reference",
            "unresolved_equation_reference",
        }:
            if link.source not in node_ids:
                warnings.append(
                    WarningRecord(
                        code="link_missing_source_node",
                        message=f"Link {link.link_id} has missing source node {link.source}.",
                        severity="error",
                        source_record_type=link.source_record_type,
                        source_record_id=link.source_record_id,
                    )
                )
            if link.target not in node_ids:
                warnings.append(
                    WarningRecord(
                        code="link_missing_target_node",
                        message=f"Link {link.link_id} has missing target node {link.target}.",
                        severity="error",
                        source_record_type=link.source_record_type,
                        source_record_id=link.source_record_id,
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


def validate_curated_paper_moa_graph(graph: CuratedPaperMoaGraph) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = []
    if graph.executable:
        warnings.append(
            WarningRecord(
                code="curated_graph_claims_executable",
                message=f"Curated graph {graph.graph_id} is marked executable.",
                severity="error",
            )
        )

    node_ids = {node.node_id for node in graph.nodes}
    edge_ids = {edge.edge_id for edge in graph.edges}
    for edge in graph.edges:
        if edge.source not in node_ids:
            warnings.append(
                WarningRecord(
                    code="curated_edge_missing_source_node",
                    message=f"Curated edge {edge.edge_id} has missing source node {edge.source}.",
                    severity="error",
                    source_record_type="curated_edge",
                    source_record_id=edge.edge_id,
                )
            )
        if edge.target not in node_ids:
            warnings.append(
                WarningRecord(
                    code="curated_edge_missing_target_node",
                    message=f"Curated edge {edge.edge_id} has missing target node {edge.target}.",
                    severity="error",
                    source_record_type="curated_edge",
                    source_record_id=edge.edge_id,
                )
            )
        if edge.review_status != "review_only":
            if not edge.evidence_anchor_ids:
                warnings.append(
                    WarningRecord(
                        code="curated_candidate_edge_missing_anchor",
                        message=f"Curated candidate edge {edge.edge_id} has no evidence anchors.",
                        severity="error",
                        source_record_type="curated_edge",
                        source_record_id=edge.edge_id,
                    )
                )
            if not edge.provenance:
                warnings.append(
                    WarningRecord(
                        code="curated_candidate_edge_missing_provenance",
                        message=f"Curated candidate edge {edge.edge_id} has no provenance records.",
                        severity="error",
                        source_record_type="curated_edge",
                        source_record_id=edge.edge_id,
                    )
                )

    for parameter in graph.parameters:
        if parameter.target_node_id and parameter.target_node_id not in node_ids:
            warnings.append(
                WarningRecord(
                    code="curated_parameter_missing_target_node",
                    message=(
                        f"Curated parameter {parameter.parameter_id} targets missing node "
                        f"{parameter.target_node_id}."
                    ),
                    severity="error",
                    source_record_type="curated_parameter",
                    source_record_id=parameter.parameter_id,
                )
            )
        if parameter.target_edge_id and parameter.target_edge_id not in edge_ids:
            warnings.append(
                WarningRecord(
                    code="curated_parameter_missing_target_edge",
                    message=(
                        f"Curated parameter {parameter.parameter_id} targets missing edge "
                        f"{parameter.target_edge_id}."
                    ),
                    severity="error",
                    source_record_type="curated_parameter",
                    source_record_id=parameter.parameter_id,
                )
            )
        if (
            parameter.role == "calibration_or_validation_endpoint"
            and parameter.review_status != "review_only"
        ):
            warnings.append(
                WarningRecord(
                    code="curated_calibration_endpoint_promoted",
                    message=f"Calibration endpoint {parameter.parameter_id} must remain review-only.",
                    severity="error",
                    source_record_type="curated_parameter",
                    source_record_id=parameter.parameter_id,
                )
            )
        if (
            parameter.review_status != "review_only"
            and parameter.role != "calibration_or_validation_endpoint"
        ):
            if parameter.value is None:
                warnings.append(
                    WarningRecord(
                        code="curated_promoted_parameter_missing_value",
                        message=f"Promoted curated parameter {parameter.parameter_id} has no value.",
                        severity="error",
                        source_record_type="curated_parameter",
                        source_record_id=parameter.parameter_id,
                    )
                )
            if parameter.unit is None:
                warnings.append(
                    WarningRecord(
                        code="curated_promoted_parameter_missing_unit",
                        message=f"Promoted curated parameter {parameter.parameter_id} has no unit.",
                        severity="error",
                        source_record_type="curated_parameter",
                        source_record_id=parameter.parameter_id,
                    )
                )
            if not (
                parameter.context.species
                or parameter.context.translation_stage
                or parameter.context.model_system
            ):
                warnings.append(
                    WarningRecord(
                        code="curated_promoted_parameter_missing_context",
                        message=f"Promoted curated parameter {parameter.parameter_id} has no species/stage context.",
                        severity="error",
                        source_record_type="curated_parameter",
                        source_record_id=parameter.parameter_id,
                    )
                )
            if not parameter.evidence_anchor_ids or not parameter.provenance:
                warnings.append(
                    WarningRecord(
                        code="curated_promoted_parameter_missing_evidence",
                        message=f"Promoted curated parameter {parameter.parameter_id} lacks evidence/provenance.",
                        severity="error",
                        source_record_type="curated_parameter",
                        source_record_id=parameter.parameter_id,
                    )
                )

    for equation in graph.equations:
        if equation.target_node_id and equation.target_node_id not in node_ids:
            warnings.append(
                WarningRecord(
                    code="curated_equation_missing_target_node",
                    message=f"Curated equation {equation.equation_id} targets missing node {equation.target_node_id}.",
                    severity="error",
                    source_record_type="curated_equation",
                    source_record_id=equation.equation_id,
                )
            )
        if equation.target_edge_id and equation.target_edge_id not in edge_ids:
            warnings.append(
                WarningRecord(
                    code="curated_equation_missing_target_edge",
                    message=f"Curated equation {equation.equation_id} targets missing edge {equation.target_edge_id}.",
                    severity="error",
                    source_record_type="curated_equation",
                    source_record_id=equation.equation_id,
                )
            )
        if not equation.expression_text:
            warnings.append(
                WarningRecord(
                    code="curated_equation_missing_expression",
                    message=f"Curated equation {equation.equation_id} has no expression text.",
                    severity="error",
                    source_record_type="curated_equation",
                    source_record_id=equation.equation_id,
                )
            )

    return tuple(warnings)


def assert_valid_curated_paper_moa_graph(graph: CuratedPaperMoaGraph) -> None:
    warnings = validate_curated_paper_moa_graph(graph)
    errors = tuple(warning for warning in warnings if warning.severity == "error")
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(messages)
