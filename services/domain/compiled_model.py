"""Typed compiled-model domain."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

from ._validation import duplicate_items, missing_items
from .base import STRICT_MODEL_CONFIG, JsonValue
from .expressions import (
    DisplayExpression,
    ExecutableOrDisplayExpression,
    expression_parameters,
    expression_states,
)
from .graph import Edge, GraphSummary
from .identifiers import (
    EdgeId,
    GraphId,
    ModifierId,
    NodeId,
    OperatorId,
    ParameterId,
    PathwayId,
    StateId,
    TermId,
)
from .parameters import ParameterCatalog
from .vocabulary import EDGE_TARGET_RELATIONS, NEGATIVE_OPERATOR_KINDS, POSITIVE_OPERATOR_KINDS, Sign
from .warnings import ModelWarning


class EquationTerm(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    state: StateId
    term_id: TermId
    expression: ExecutableOrDisplayExpression
    operator: OperatorId
    sign: Sign
    source_edges: tuple[EdgeId, ...]
    modifiers: tuple[EdgeId, ...] = ()
    parameters: tuple[ParameterId, ...] = ()
    description: str = Field(min_length=1)


class ModifierTerm(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    modifier_id: ModifierId
    target_edge: EdgeId
    expression: ExecutableOrDisplayExpression
    operator: OperatorId
    source_edges: tuple[EdgeId, ...]
    parameters: tuple[ParameterId, ...]
    description: str = Field(min_length=1)


class StateEquation(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    state: StateId
    terms: tuple[TermId, ...]
    expression: ExecutableOrDisplayExpression
    source_edges: tuple[EdgeId, ...]
    parameters: tuple[ParameterId, ...]


class SourceGraphNode(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: NodeId
    type: str
    state: StateId | None = None
    roles: tuple[str, ...] = ()


class SourceGraphEdge(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: EdgeId
    source: NodeId
    target_node: NodeId | None = None
    target_edge: EdgeId | None = None
    relation: str
    sign: Sign
    operator: OperatorId | None = None

    @model_validator(mode="after")
    def target_shape_matches_relation(self) -> SourceGraphEdge:
        if self.relation in EDGE_TARGET_RELATIONS:
            if self.target_edge is None or self.target_node is not None:
                raise ValueError(f"Modifier edge {self.id} must carry target_edge only")
        elif self.target_node is None or self.target_edge is not None:
            raise ValueError(f"Causal edge {self.id} must carry target_node only")
        return self

    @classmethod
    def from_graph_edge(cls, edge: Edge) -> SourceGraphEdge:
        if str(edge.relation) in EDGE_TARGET_RELATIONS:
            return cls(
                id=edge.id,
                source=edge.source,
                target_edge=EdgeId(str(edge.target)),
                relation=str(edge.relation),
                sign=edge.sign,
                operator=edge.operator,
            )
        return cls(
            id=edge.id,
            source=edge.source,
            target_node=NodeId(str(edge.target)),
            relation=str(edge.relation),
            sign=edge.sign,
            operator=edge.operator,
        )


class CompiledModelMetadata(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    selected_configuration: str | None = None
    included_modules: tuple[str, ...] = ()
    drug_effects: tuple[str, ...] = ()
    drug_state: StateId | None = None
    endpoint_states: tuple[StateId, ...] = ()
    plot_states: tuple[StateId, ...] = ()
    initial_conditions: dict[StateId, float]
    logic_checks: tuple[dict[str, JsonValue], ...] = ()
    execution_model: str = Field(min_length=1)
    expressions_execute_directly: bool
    graph_summary: GraphSummary
    source_graph_nodes: tuple[SourceGraphNode, ...]
    source_graph_edges: tuple[SourceGraphEdge, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CompiledReferenceIndex:
    states: frozenset[StateId]
    graph_edge_by_id: dict[EdgeId, SourceGraphEdge]
    graph_edge_ids: frozenset[EdgeId]
    known_parameters: frozenset[ParameterId]
    known_term_ids: frozenset[TermId]
    known_modifier_edge_ids: frozenset[EdgeId]


class CompiledModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    graph_id: GraphId
    label: str = Field(min_length=1)
    states: tuple[StateId, ...]
    terms: tuple[EquationTerm, ...]
    modifiers: tuple[ModifierTerm, ...] = ()
    equations: tuple[StateEquation, ...]
    parameter_catalog: ParameterCatalog
    warnings: tuple[ModelWarning, ...] = ()
    metadata: CompiledModelMetadata

    @model_validator(mode="after")
    def validate_compiled_references(self) -> CompiledModel:
        self._validate_unique_model_keys()
        index = self._reference_index()

        for term in self.terms:
            self._validate_term_references(term, index)
        for modifier in self.modifiers:
            self._validate_modifier_references(modifier, index)
        for equation in self.equations:
            self._validate_equation_references(equation, index)
        return self

    def _validate_unique_model_keys(self) -> None:
        state_set = frozenset(self.states)
        if len(self.states) != len(state_set):
            raise ValueError("Compiled model states must be unique")

        term_ids = tuple(term.term_id for term in self.terms)
        modifier_ids = tuple(modifier.modifier_id for modifier in self.modifiers)
        equation_states = tuple(equation.state for equation in self.equations)
        duplicate_terms = duplicate_items(term_ids)
        duplicate_modifiers = duplicate_items(modifier_ids)
        if duplicate_terms:
            raise ValueError(f"Duplicate term ids: {list(duplicate_terms)}")
        if duplicate_modifiers:
            raise ValueError(f"Duplicate modifier ids: {list(duplicate_modifiers)}")
        if frozenset(equation_states) != state_set or len(equation_states) != len(state_set):
            raise ValueError("Compiled model must include exactly one equation per executable state")

    def _reference_index(self) -> _CompiledReferenceIndex:
        graph_edge_by_id = {edge.id: edge for edge in self.metadata.source_graph_edges}
        return _CompiledReferenceIndex(
            states=frozenset(self.states),
            graph_edge_by_id=graph_edge_by_id,
            graph_edge_ids=frozenset(graph_edge_by_id),
            known_parameters=self.parameter_catalog.known_parameter_ids(),
            known_term_ids=frozenset(term.term_id for term in self.terms),
            known_modifier_edge_ids=frozenset(EdgeId(str(modifier.modifier_id)) for modifier in self.modifiers),
        )

    def _validate_term_references(self, term: EquationTerm, index: _CompiledReferenceIndex) -> None:
        if term.state not in index.states:
            raise ValueError(f"Term {term.term_id} targets state {term.state!r} outside model states")

        self._validate_expression_mode("term", str(term.term_id), term.expression)
        self._raise_if_missing(
            missing_items(term.source_edges, index.graph_edge_ids),
            f"Term {term.term_id} references unknown source edges",
        )
        self._raise_if_missing(
            missing_items(term.modifiers, index.known_modifier_edge_ids),
            f"Term {term.term_id} references unknown modifier edges",
        )
        for modifier_id in term.modifiers:
            self._validate_term_modifier_target(term, modifier_id, index)

        self._validate_declared_parameters(f"Term {term.term_id}", term.parameters, index)
        self._validate_expression_references(f"Term {term.term_id}", term.expression, index)
        self._validate_term_sign(term)

    def _validate_term_modifier_target(
        self,
        term: EquationTerm,
        modifier_id: EdgeId,
        index: _CompiledReferenceIndex,
    ) -> None:
        modifier_edge = index.graph_edge_by_id.get(modifier_id)
        if modifier_edge is None or modifier_edge.relation not in EDGE_TARGET_RELATIONS:
            raise ValueError(f"Term {term.term_id} modifier {modifier_id} is not an edge modifier")
        if modifier_edge.target_edge not in term.source_edges:
            raise ValueError(f"Term {term.term_id} modifier {modifier_id} does not target one of its source edges")

    def _validate_modifier_references(
        self,
        modifier: ModifierTerm,
        index: _CompiledReferenceIndex,
    ) -> None:
        modifier_edge_id = EdgeId(str(modifier.modifier_id))
        modifier_edge = index.graph_edge_by_id.get(modifier_edge_id)
        if modifier_edge is None:
            raise ValueError(f"Modifier {modifier.modifier_id} is not present in the source graph")
        if modifier_edge.relation not in EDGE_TARGET_RELATIONS:
            raise ValueError(f"Modifier {modifier.modifier_id} is not an edge-modifier relation")
        if modifier_edge.target_edge != modifier.target_edge:
            raise ValueError(f"Modifier {modifier.modifier_id} target {modifier.target_edge} does not match source graph")

        self._validate_expression_mode("modifier", str(modifier.modifier_id), modifier.expression)
        missing_edges = list(missing_items(modifier.source_edges, index.graph_edge_ids))
        if modifier.target_edge not in index.graph_edge_ids:
            missing_edges.append(modifier.target_edge)
        self._raise_if_missing(missing_edges, f"Modifier {modifier.modifier_id} references unknown source edges")

        if modifier_edge_id not in modifier.source_edges or modifier.target_edge not in modifier.source_edges:
            raise ValueError(f"Modifier {modifier.modifier_id} source_edges must include modifier and target edge ids")

        self._validate_declared_parameters(f"Modifier {modifier.modifier_id}", modifier.parameters, index)
        self._validate_expression_references(f"Modifier {modifier.modifier_id}", modifier.expression, index)

    def _validate_equation_references(
        self,
        equation: StateEquation,
        index: _CompiledReferenceIndex,
    ) -> None:
        self._validate_expression_mode("equation", str(equation.state), equation.expression)
        self._raise_if_missing(
            missing_items(equation.terms, index.known_term_ids),
            f"Equation {equation.state} references unknown terms",
        )
        self._raise_if_missing(
            missing_items(equation.source_edges, index.graph_edge_ids),
            f"Equation {equation.state} references unknown edges",
        )
        self._validate_declared_parameters(f"Equation {equation.state}", equation.parameters, index)
        self._validate_expression_references(f"Equation {equation.state}", equation.expression, index)

    def _validate_expression_mode(
        self,
        artifact_type: str,
        artifact_id: str,
        expression: ExecutableOrDisplayExpression,
    ) -> None:
        uses_display_expression = isinstance(expression, DisplayExpression)
        subject = f"{artifact_type} {artifact_id}"
        if self.metadata.expressions_execute_directly and uses_display_expression:
            raise ValueError(f"Executable compiled model {subject} cannot use DisplayExpression")
        if not self.metadata.expressions_execute_directly and not uses_display_expression:
            raise ValueError(f"Display-only compiled model {subject} cannot use executable IR")

    def _validate_declared_parameters(
        self,
        owner: str,
        parameters: tuple[ParameterId, ...],
        index: _CompiledReferenceIndex,
    ) -> None:
        self._raise_if_missing(missing_items(parameters, index.known_parameters), f"{owner} references unknown parameters")

    def _validate_expression_references(
        self,
        owner: str,
        expression: ExecutableOrDisplayExpression,
        index: _CompiledReferenceIndex,
    ) -> None:
        if not self.metadata.expressions_execute_directly:
            return

        self._raise_if_missing(
            missing_items(expression_parameters(expression), index.known_parameters),
            f"{owner} expression references unknown parameters",
        )
        missing_states = tuple(str(state) for state in expression_states(expression) if state not in index.states)
        self._raise_if_missing(missing_states, f"{owner} expression references states outside model")

    @staticmethod
    def _raise_if_missing(missing: Sequence[object], message: str) -> None:
        if missing:
            raise ValueError(f"{message}: {list(missing)}")

    @staticmethod
    def _validate_term_sign(term: EquationTerm) -> None:
        operator = str(term.operator)
        if operator in POSITIVE_OPERATOR_KINDS and term.sign == Sign.NEGATIVE:
            raise ValueError(f"Term {term.term_id} has negative sign for positive operator {operator}")
        if operator in NEGATIVE_OPERATOR_KINDS and term.sign == Sign.POSITIVE:
            raise ValueError(f"Term {term.term_id} has positive sign for negative operator {operator}")

    def terms_for_state(self, state: StateId | str) -> tuple[EquationTerm, ...]:
        state_id = StateId(str(state))
        return tuple(term for term in self.terms if term.state == state_id)
