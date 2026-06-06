"""Typed graph domain models with pathway-defined identifiers."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

from ._validation import duplicate_items
from .base import STRICT_MODEL_CONFIG, JsonValue, Probability
from .expressions import Expression
from .identifiers import EdgeId, GraphId, NodeId, NodeTypeId, OperatorId, PathwayId, RelationId, StateId
from .vocabulary import EDGE_TARGET_RELATIONS, EvidenceSourceType, Sign, relation_default_sign


class DatabaseRef(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    namespace: str = Field(min_length=1)
    identifier: str = Field(min_length=1)
    url: str | None = None


class NodeMetadata(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    database_refs: tuple[DatabaseRef, ...] = ()
    compartment: str | None = None
    extension: dict[str, JsonValue] = Field(default_factory=dict)


class EdgeMetadata(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    assay_direction: str | None = None
    temporal_order: str | None = None
    extension: dict[str, JsonValue] = Field(default_factory=dict)


class Evidence(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    source_type: EvidenceSourceType = EvidenceSourceType.CURATED_ASSUMPTION
    source_label: str | None = None
    description: str = Field(min_length=1)
    reference: str | None = None
    confidence: Probability | None = None

    @model_validator(mode="after")
    def require_other_label(self) -> Evidence:
        if self.source_type == EvidenceSourceType.OTHER and not (self.source_label or "").strip():
            raise ValueError("Evidence source_type='other' requires source_label.")
        return self


class BiologicalContext(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    species: str = "human"
    cell_type: str | None = None
    assay: str | None = None
    endpoint: str | None = None
    notes: str | None = None
    extension: dict[str, JsonValue] = Field(default_factory=dict)


class StateBinding(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: StateId
    executable: bool = True
    initial: float | None = None


class Node(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: NodeId
    label: str = Field(min_length=1)
    type: NodeTypeId
    aliases: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    state: StateBinding | None = None
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)


class Edge(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: EdgeId
    source: NodeId
    target: NodeId | EdgeId
    relation: RelationId
    sign: Sign
    confidence: Probability = 0.8
    evidence: tuple[Evidence, ...] = ()
    operator: OperatorId | None = None
    expression: Expression | None = None
    description: str | None = None
    is_hypothesis: bool = False
    hypothesis_rationale: str | None = None
    metadata: EdgeMetadata = Field(default_factory=EdgeMetadata)

    @model_validator(mode="after")
    def sign_matches_relation(self) -> Edge:
        expected_sign = relation_default_sign(str(self.relation))
        if expected_sign == Sign.NEGATIVE and self.sign == Sign.POSITIVE:
            raise ValueError(f"{self.relation} edges should not have positive sign")
        if expected_sign == Sign.POSITIVE and self.sign == Sign.NEGATIVE:
            raise ValueError(f"{self.relation} edges should not have negative sign")
        return self


class GraphSummary(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    graph_id: GraphId
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    edge_relations: tuple[RelationId, ...]
    context: BiologicalContext


class GraphMetadata(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    configuration: str | None = None
    included_modules: tuple[str, ...] = ()
    drug_effects: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    drug_state: StateId | None = None
    endpoint_states: tuple[StateId, ...] = ()
    source: str = "pathway_composer"
    extension: dict[str, JsonValue] = Field(default_factory=dict)


@dataclass(frozen=True)
class _GraphReferenceIndex:
    node_ids: frozenset[NodeId]
    edge_ids: frozenset[EdgeId]


class MoAGraph(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    graph_id: GraphId
    label: str = Field(min_length=1)
    context: BiologicalContext = Field(default_factory=BiologicalContext)
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    source_claim: str | None = None
    version: str = "1.0"
    metadata: GraphMetadata

    @model_validator(mode="after")
    def validate_references_and_uniqueness(self) -> MoAGraph:
        index = self._validate_unique_graph_keys()
        self._validate_edge_references(index)
        return self

    def _validate_unique_graph_keys(self) -> _GraphReferenceIndex:
        node_ids = tuple(node.id for node in self.nodes)
        edge_ids = tuple(edge.id for edge in self.edges)
        duplicate_nodes = duplicate_items(node_ids)
        duplicate_edges = duplicate_items(edge_ids)
        if duplicate_nodes:
            raise ValueError(f"Duplicate node ids: {list(duplicate_nodes)}")
        if duplicate_edges:
            raise ValueError(f"Duplicate edge ids: {list(duplicate_edges)}")

        bindings = tuple(node.state.id for node in self.nodes if node.state is not None)
        duplicate_bindings = duplicate_items(bindings)
        if duplicate_bindings:
            raise ValueError(f"Duplicate state bindings: {list(duplicate_bindings)}")

        return _GraphReferenceIndex(node_ids=frozenset(node_ids), edge_ids=frozenset(edge_ids))

    def _validate_edge_references(self, index: _GraphReferenceIndex) -> None:
        causal_edge_tuples: set[tuple[str, str, RelationId]] = set()
        for edge in self.edges:
            self._validate_edge_source(edge, index)
            if str(edge.relation) in EDGE_TARGET_RELATIONS:
                self._validate_modifier_edge_target(edge, index)
            else:
                self._validate_causal_edge_target(edge, index, causal_edge_tuples)
            self._validate_edge_evidence(edge)

    @staticmethod
    def _validate_edge_source(edge: Edge, index: _GraphReferenceIndex) -> None:
        if edge.source not in index.node_ids:
            raise ValueError(f"Edge {edge.id} source {edge.source!r} is not a node id")

    @staticmethod
    def _validate_modifier_edge_target(edge: Edge, index: _GraphReferenceIndex) -> None:
        if EdgeId(str(edge.target)) not in index.edge_ids:
            raise ValueError(f"Edge modifier {edge.id} target {edge.target!r} must reference an edge id")

    @staticmethod
    def _validate_causal_edge_target(
        edge: Edge,
        index: _GraphReferenceIndex,
        causal_edge_tuples: set[tuple[str, str, RelationId]],
    ) -> None:
        if NodeId(str(edge.target)) not in index.node_ids:
            raise ValueError(f"Edge {edge.id} target {edge.target!r} is not a node id")
        if edge.source == edge.target:
            raise ValueError(f"Edge {edge.id} is a self-loop; causal graph edges must connect distinct nodes")

        edge_tuple = (str(edge.source), str(edge.target), edge.relation)
        if edge_tuple in causal_edge_tuples:
            raise ValueError(
                f"Duplicate causal edge tuple ({edge.source!r}, {edge.target!r}, {edge.relation!r})"
            )
        causal_edge_tuples.add(edge_tuple)

    @staticmethod
    def _validate_edge_evidence(edge: Edge) -> None:
        if not edge.is_hypothesis and not edge.evidence:
            raise ValueError(f"Edge {edge.id} requires at least one evidence entry")
        if edge.is_hypothesis and not edge.evidence and not (edge.hypothesis_rationale or "").strip():
            raise ValueError(f"Hypothesis edge {edge.id} requires evidence or hypothesis_rationale")

    def node_map(self) -> dict[NodeId, Node]:
        return {node.id: node for node in self.nodes}

    def edge_map(self) -> dict[EdgeId, Edge]:
        return {edge.id: edge for edge in self.edges}

    def node_type(self, node_id: NodeId) -> NodeTypeId:
        return self.node_map()[node_id].type

    def state_for_node(self, node_id: NodeId) -> StateId | None:
        node = self.node_map().get(node_id)
        if node is None or node.state is None or not node.state.executable:
            return None
        return node.state.id

    def node_for_state(self, state: StateId | str) -> Node | None:
        state_id = StateId(str(state))
        return next((node for node in self.nodes if node.state is not None and node.state.id == state_id), None)

    def drug_state(self) -> StateId | None:
        if self.metadata.drug_state is not None:
            return self.metadata.drug_state
        for node in self.nodes:
            if "drug" in node.roles and node.state is not None:
                return node.state.id
        for node in self.nodes:
            if str(node.type) == "perturbation" and node.state is not None:
                return node.state.id
        return None

    def edge_target_state(self, edge: Edge) -> StateId | None:
        if str(edge.relation) in EDGE_TARGET_RELATIONS:
            return None
        return self.state_for_node(NodeId(str(edge.target)))

    def edge_source_state(self, edge: Edge) -> StateId | None:
        return self.state_for_node(edge.source)

    def edges_for_target(self, target: NodeId | EdgeId) -> tuple[Edge, ...]:
        return tuple(edge for edge in self.edges if edge.target == target)

    def modifiers_for_edge(self, edge_id: EdgeId) -> tuple[Edge, ...]:
        return tuple(edge for edge in self.edges if edge.target == edge_id and str(edge.relation) in EDGE_TARGET_RELATIONS)

    def structural_edges(self) -> tuple[Edge, ...]:
        return tuple(edge for edge in self.edges if str(edge.relation) not in EDGE_TARGET_RELATIONS)

    def modifier_edges(self) -> tuple[Edge, ...]:
        return tuple(edge for edge in self.edges if str(edge.relation) in EDGE_TARGET_RELATIONS)

    def summarize(self) -> GraphSummary:
        return GraphSummary(
            graph_id=self.graph_id,
            node_count=len(self.nodes),
            edge_count=len(self.edges),
            edge_relations=tuple(sorted({edge.relation for edge in self.edges}, key=str)),
            context=self.context,
        )
