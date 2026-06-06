"""Candidate graph patches for the data-defined MoA predictor."""

from __future__ import annotations

import re
from dataclasses import dataclass

from services.domain import (
    Edge,
    EdgeId,
    MoAGraph,
    NodeId,
    OperatorId,
    RelationId,
    Sign,
    relation_default_sign,
)
from services.pathway.models import PredictionDefinition

_EDGE_ID_SAFE = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class CandidatePatch:
    edge_id: EdgeId
    source: NodeId
    target: EdgeId
    relation: RelationId
    sign: Sign
    operator: OperatorId
    rationale: str


def choose_prediction_source(graph: MoAGraph, source_node_id: NodeId | None = None) -> NodeId:
    if source_node_id is not None:
        if source_node_id not in graph.node_map():
            raise ValueError(f"Prediction source node {source_node_id!r} is not present in graph")
        return source_node_id
    for node in graph.nodes:
        if "drug" in node.roles:
            return node.id
    for node in graph.nodes:
        if str(node.type) == "perturbation":
            return node.id
    raise ValueError("Prediction graph must contain a perturbation/drug source node")


def operator_for_relation(relation: RelationId) -> OperatorId:
    if str(relation) == "inhibits_edge":
        return OperatorId("edge_inhibition")
    if str(relation) == "activates_edge":
        return OperatorId("edge_activation")
    return OperatorId(f"edge_{relation}")


def candidate_edge_id(source: NodeId, relation: RelationId, target: EdgeId) -> EdgeId:
    raw = f"e_predicted_{source}_{relation}_{target}"
    return EdgeId(_EDGE_ID_SAFE.sub("_", raw))


def candidate_rationale(graph: MoAGraph, target_edge: Edge, relation: RelationId) -> str:
    node_map = graph.node_map()
    source = node_map[target_edge.source].label
    target = node_map[NodeId(str(target_edge.target))].label
    direction = "activate" if str(relation) == "activates_edge" else "inhibit"
    return f"Data-defined graph-patch ranker proposes that the drug should {direction} {source} -> {target}."


def generate_edge_patch_candidates(
    graph: MoAGraph,
    prediction: PredictionDefinition,
    *,
    source_node_id: NodeId | None = None,
) -> tuple[CandidatePatch, ...]:
    source = choose_prediction_source(graph, source_node_id)
    candidates: list[CandidatePatch] = []
    for edge in graph.structural_edges():
        target = EdgeId(str(edge.id))
        for relation in prediction.allowed_modifier_relations:
            sign = relation_default_sign(str(relation))
            if sign == Sign.UNKNOWN:
                continue
            candidates.append(
                CandidatePatch(
                    edge_id=candidate_edge_id(source, relation, target),
                    source=source,
                    target=target,
                    relation=relation,
                    sign=sign,
                    operator=operator_for_relation(relation),
                    rationale=candidate_rationale(graph, edge, relation),
                )
            )
    return tuple(candidates)
