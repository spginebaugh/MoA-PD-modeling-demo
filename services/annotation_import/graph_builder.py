"""Build non-executable paper evidence graphs from annotation bundles."""

from __future__ import annotations

from services.annotation_import.converters import (
    candidate_to_parameter,
    equation_to_evidence,
    mechanism_step_to_edge,
    observation_to_parameter,
    simulation_model_to_evidence,
    simulation_parameter_to_evidence,
)
from services.annotation_import.graph_linker import connect_evidence_graph
from services.annotation_import.models import (
    AnnotationBundle,
    EvidenceEquation,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    EvidenceParameter,
    EvidenceSimulationModel,
    EvidenceSimulationParameter,
    PaperEvidenceGraph,
)
from services.annotation_import.provenance import anchor_index
from services.annotation_import.review_policy import projection_warnings, readiness_warnings
from services.annotation_import.summary import evidence_graph_summary


def build_paper_evidence_graph(bundle: AnnotationBundle) -> PaperEvidenceGraph:
    anchors = anchor_index(bundle.evidence_anchors)
    warnings = list(projection_warnings(bundle))
    warnings.extend(readiness_warnings(bundle))

    verification_by_step = {
        (verification.mechanism_chain_id, verification.mechanism_step_id): verification
        for verification in bundle.mechanism_verifications
    }

    nodes: dict[str, EvidenceGraphNode] = {}
    edges: list[EvidenceGraphEdge] = []
    for chain in bundle.mechanism_chains:
        for step in chain.steps:
            verification = verification_by_step.get((chain.mechanism_chain_id, step.step_id))
            edge_nodes, edge = mechanism_step_to_edge(bundle, chain, step, verification, anchors)
            for node in edge_nodes:
                nodes.setdefault(node.node_id, node)
            edges.append(edge)

    parameters: list[EvidenceParameter] = [
        *(candidate_to_parameter(bundle, candidate, anchors) for candidate in bundle.parameter_candidates),
        *(observation_to_parameter(bundle, observation, anchors) for observation in bundle.observations),
    ]
    equations: list[EvidenceEquation] = [
        equation_to_evidence(bundle, equation, anchors) for equation in bundle.equations
    ]
    simulation_models: list[EvidenceSimulationModel] = [
        simulation_model_to_evidence(bundle, model, anchors) for model in bundle.simulation_models
    ]
    simulation_parameters: list[EvidenceSimulationParameter] = [
        simulation_parameter_to_evidence(bundle, parameter, anchors)
        for parameter in bundle.simulation_parameters
    ]
    links = connect_evidence_graph(
        bundle=bundle,
        nodes=nodes,
        edges=edges,
        parameters=parameters,
        equations=equations,
        simulation_models=simulation_models,
        simulation_parameters=simulation_parameters,
        anchors=anchors,
    )
    node_values = tuple(nodes.values())

    return PaperEvidenceGraph(
        paper_id=bundle.paper.paper_id,
        title=bundle.paper.title,
        source=bundle.paper.source,
        nodes=node_values,
        edges=tuple(edges),
        links=tuple(links),
        parameters=tuple(parameters),
        equations=tuple(equations),
        simulation_models=tuple(simulation_models),
        simulation_parameters=tuple(simulation_parameters),
        evidence_anchors=bundle.evidence_anchors,
        warnings=tuple(warnings),
        summary=evidence_graph_summary(
            bundle,
            node_values,
            edges,
            links,
            parameters,
            equations,
            simulation_models,
            simulation_parameters,
            warnings,
        ),
    )
