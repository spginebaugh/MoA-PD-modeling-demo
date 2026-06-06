"""Typed warning objects shared across compiler, simulator, and predictor."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .base import STRICT_MODEL_CONFIG, JsonValue
from .identifiers import EdgeId, ParameterId, StateId, TermId
from .vocabulary import WarningCategory, WarningSeverity


class EdgeWarningSource(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["edge"] = "edge"
    id: EdgeId


class TermWarningSource(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["term"] = "term"
    id: TermId


class ParameterWarningSource(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["parameter"] = "parameter"
    id: ParameterId


class StateWarningSource(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["state"] = "state"
    id: StateId


WarningSource = Annotated[
    EdgeWarningSource | TermWarningSource | ParameterWarningSource | StateWarningSource,
    Field(discriminator="kind"),
]


class ModelWarning(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    category: WarningCategory
    severity: WarningSeverity = WarningSeverity.WARNING
    message: str = Field(min_length=1)
    source: WarningSource | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


def edge_source(edge_id: EdgeId | str) -> EdgeWarningSource:
    return EdgeWarningSource(id=EdgeId(str(edge_id)))


def term_source(term_id: TermId | str) -> TermWarningSource:
    return TermWarningSource(id=TermId(str(term_id)))


def parameter_source(parameter_id: ParameterId | str) -> ParameterWarningSource:
    return ParameterWarningSource(id=ParameterId(str(parameter_id)))


def state_source(state: StateId | str) -> StateWarningSource:
    return StateWarningSource(id=StateId(str(state)))
