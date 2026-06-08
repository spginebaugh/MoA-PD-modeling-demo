"""Summary generation for annotation evidence graphs."""

from __future__ import annotations

from collections import Counter

from services.annotation_import.models import (
    AnnotationBundle,
    EvidenceEquation,
    EvidenceGraphEdge,
    EvidenceGraphLink,
    EvidenceGraphNode,
    EvidenceParameter,
    EvidenceSimulationModel,
    EvidenceSimulationParameter,
    WarningRecord,
)
from services.annotation_import.review_policy import projection_node_count
from services.domain.base import JsonValue


def evidence_graph_summary(
    bundle: AnnotationBundle,
    nodes: tuple[EvidenceGraphNode, ...],
    edges: list[EvidenceGraphEdge],
    links: list[EvidenceGraphLink],
    parameters: list[EvidenceParameter],
    equations: list[EvidenceEquation],
    simulation_models: list[EvidenceSimulationModel],
    simulation_parameters: list[EvidenceSimulationParameter],
    warnings: list[WarningRecord],
) -> dict[str, JsonValue]:
    edge_status_counts = Counter(edge.review_status for edge in edges)
    link_relation_counts = Counter(link.relation for link in links)
    node_type_counts = Counter(node.node_type for node in nodes)
    parameter_status_counts = Counter(parameter.review_status for parameter in parameters)
    simulation_parameter_roles = Counter(parameter.role for parameter in simulation_parameters)
    return {
        "top_level_mechanism_chain_count": len(bundle.mechanism_chains),
        "top_level_mechanism_step_count": sum(len(chain.steps) for chain in bundle.mechanism_chains),
        "top_level_mechanism_verification_count": len(bundle.mechanism_verifications),
        "kg_projection_mechanism_node_count": projection_node_count(bundle, "tktype:MechanismChain"),
        "kg_projection_verification_node_count": projection_node_count(
            bundle, "tktype:MechanismVerification"
        ),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "link_count": len(links),
        "parameter_count": len(parameters),
        "equation_count": len(equations),
        "simulation_model_count": len(simulation_models),
        "simulation_parameter_count": len(simulation_parameters),
        "scientific_symbol_count": len(bundle.scientific_symbols),
        "study_design_count": len(bundle.study_designs),
        "figure_annotation_count": len(bundle.figure_annotations),
        "evidence_anchor_count": len(bundle.evidence_anchors),
        "warning_count": len(warnings),
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "link_relation_counts": dict(sorted(link_relation_counts.items())),
        "edge_review_status_counts": dict(sorted(edge_status_counts.items())),
        "parameter_review_status_counts": dict(sorted(parameter_status_counts.items())),
        "simulation_parameter_role_counts": dict(sorted(simulation_parameter_roles.items())),
        "runtime_executable": False,
    }
