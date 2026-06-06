"""Runtime-validated, statically distinct domain identifiers."""

from __future__ import annotations

from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

ID_PATTERN = r"^[A-Za-z0-9_.:-]+$"


class DomainId(str):
    """Base class for domain identifiers that serialize as strings."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(min_length=1, pattern=ID_PATTERN),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def validate(cls, value: str) -> Self:
        return cls(value)


class PathwayId(DomainId):
    """Identifier for a pathway definition."""


class ConfigurationId(DomainId):
    """Identifier for a pathway graph composition recipe."""


class ModuleId(DomainId):
    """Identifier for an optional pathway module."""


class DrugEffectId(DomainId):
    """Identifier for a predefined drug effect bundle."""


class NodeId(DomainId):
    """Identifier for a graph node."""


class EdgeId(DomainId):
    """Identifier for a graph edge."""


class TermId(DomainId):
    """Identifier for a compiled equation term."""


class ModifierId(EdgeId):
    """Identifier for an edge-modifier term, tied to its source graph edge."""


class ParameterId(DomainId):
    """Identifier for a parameter."""


class GraphId(DomainId):
    """Identifier for a graph artifact."""


class StateId(DomainId):
    """Identifier for an executable dynamic state."""


class RelationId(DomainId):
    """Identifier for an edge relation."""


class OperatorId(DomainId):
    """Identifier for an equation operator."""


class NodeTypeId(DomainId):
    """Identifier for a pathway-defined node type."""


def node_id(value: str) -> NodeId:
    return NodeId(value)


def edge_id(value: str) -> EdgeId:
    return EdgeId(value)


def term_id(value: str) -> TermId:
    return TermId(value)


def modifier_id(value: str) -> ModifierId:
    return ModifierId(value)


def parameter_id(value: str) -> ParameterId:
    return ParameterId(value)


def graph_id(value: str) -> GraphId:
    return GraphId(value)


def state_id(value: str) -> StateId:
    return StateId(value)
