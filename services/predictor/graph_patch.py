"""Apply prediction-derived graph patches."""

from __future__ import annotations

from services.domain import (
    EDGE_TARGET_RELATIONS,
    Edge,
    EdgeMetadata,
    EdgeRecommendation,
    Evidence,
    EvidenceSourceType,
    GraphId,
    MoAGraph,
    ModuleId,
    PathwayId,
)
from services.domain._validation import duplicate_items
from services.pathway.composer import compose_graph
from services.pathway.models import GraphComposeRequest


def _patch_confidence(support_score: float) -> float:
    return min(max(support_score, 0.2), 0.75)


def _hypothesis_edge(recommendation: EdgeRecommendation, *, claim_text: str, decision_source: str) -> Edge:
    evidence_description = (
        f"Prediction-derived hypothesis from claim: {claim_text}"
        if claim_text.strip()
        else "Prediction-derived hypothesis edge."
    )
    return Edge(
        id=recommendation.edge_id,
        source=recommendation.source,
        target=recommendation.target,
        relation=recommendation.relation,
        sign=recommendation.sign,
        confidence=_patch_confidence(recommendation.support_score),
        evidence=(
            Evidence(
                source_type=EvidenceSourceType.CLAIM,
                source_label="prediction",
                description=evidence_description,
                confidence=_patch_confidence(recommendation.support_score),
            ),
        ),
        is_hypothesis=True,
        hypothesis_rationale=recommendation.rationale,
        metadata=EdgeMetadata(
            extension={
                "prediction_decision_source": decision_source,
                "prediction_support_score": recommendation.support_score,
            }
        ),
    )


def _prediction_base_graph(graph: MoAGraph) -> MoAGraph:
    base_edges = tuple(edge for edge in graph.edges if str(edge.relation) not in EDGE_TARGET_RELATIONS)
    return graph.model_copy(
        update={
            "graph_id": GraphId(f"{graph.graph_id}_prediction_base"),
            "label": f"{graph.label} prediction base",
            "edges": base_edges,
        }
    )


def apply_edge_recommendations(
    graph: MoAGraph | None,
    recommendations: tuple[EdgeRecommendation, ...],
    *,
    claim_text: str = "",
    decision_source: str,
    pathway_id: str,
    include_modules: tuple[str, ...] = (),
) -> MoAGraph:
    base_graph = (
        compose_graph(
            GraphComposeRequest(
                pathway_id=PathwayId(pathway_id),
                include_modules=tuple(ModuleId(module) for module in include_modules),
                source_claim=claim_text or None,
            )
        )
        if graph is None
        else _prediction_base_graph(graph)
    )
    node_map = base_graph.node_map()
    edge_map = base_graph.edge_map()
    if not recommendations:
        raise ValueError("At least one prediction recommendation is required")
    duplicate_recommendations = duplicate_items(
        tuple(recommendation.edge_id for recommendation in recommendations)
    )
    if duplicate_recommendations:
        raise ValueError(f"Duplicate recommendation edge ids: {list(duplicate_recommendations)}")

    for recommendation in recommendations:
        if recommendation.source not in node_map:
            raise ValueError(f"Recommendation source {recommendation.source!r} is not present in graph")
        if str(recommendation.relation) not in EDGE_TARGET_RELATIONS:
            raise ValueError("Prediction recommendations must use edge-modifier relations")
        if recommendation.target not in edge_map:
            raise ValueError(f"Recommendation target edge {recommendation.target!r} is not present in graph")
        if recommendation.edge_id in edge_map:
            raise ValueError(f"Recommendation edge id {recommendation.edge_id!r} already exists in graph")

    hypothesis_edges = tuple(
        _hypothesis_edge(recommendation, claim_text=claim_text, decision_source=decision_source)
        for recommendation in recommendations
    )
    return base_graph.model_copy(
        update={
            "graph_id": GraphId(f"{base_graph.graph_id}_predicted_patches"),
            "label": f"{base_graph.label} with predicted patches",
            "source_claim": claim_text or base_graph.source_claim,
            "edges": (*base_graph.edges, *hypothesis_edges),
        }
    )
