"""API transport envelopes for the data-driven MoA-to-PD domain."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from services.annotation_import.models import PaperEvidenceGraph, PathwayProposal
from services.domain import (
    CompiledModel,
    MoAGraph,
    ModelWarning,
    OperatorPrediction,
    OperatorPredictionInput,
    ParameterId,
    PathwayId,
    SimulationResult,
    SimulationSettings,
    StateId,
    WarningCategory,
    WarningSeverity,
)
from services.domain.base import STRICT_MODEL_CONFIG, JsonValue
from services.domain.warnings import WarningSource
from services.pathway.models import GraphComposeRequest, PathwayContract, PathwayDefinition, PathwaySummary


class ErrorLocation(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    path: tuple[str | int, ...] = ()


class ApiError(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    category: WarningCategory
    severity: WarningSeverity = WarningSeverity.ERROR
    message: str
    source: WarningSource | None = None
    location: ErrorLocation | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[False] = False
    errors: tuple[ApiError, ...]
    warnings: tuple[ModelWarning, ...] = ()


class HealthResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    status: str
    service: str
    pathways: tuple[PathwayId, ...]


class PathwaysResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    pathways: tuple[PathwaySummary, ...]


class PathwayResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    pathway: PathwayDefinition


class PathwayContractResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    contract: PathwayContract


class GraphComposeResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    graph: MoAGraph
    warnings: tuple[ModelWarning, ...] = ()


class CompileRequest(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    graph: MoAGraph


class CompileStatus(StrEnum):
    READY = "ready"
    DIAGNOSTIC_ONLY = "diagnostic_only"


class CompileResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: bool
    status: CompileStatus
    model: CompiledModel
    warnings: tuple[ModelWarning, ...] = ()
    errors: tuple[ModelWarning, ...] = ()


class SimulateRequest(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId | None = None
    graph: MoAGraph | None = None
    compiled_model: CompiledModel | None = None
    settings: SimulationSettings = Field(default_factory=SimulationSettings)
    parameter_overrides: dict[ParameterId, float] = Field(default_factory=dict)
    initial_condition_overrides: dict[StateId, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def exactly_one_model_source(self) -> SimulateRequest:
        provided = sum(item is not None for item in [self.graph, self.compiled_model])
        if provided != 1:
            raise ValueError("Provide exactly one of graph or compiled_model.")
        if self.graph is not None and self.pathway_id is None:
            raise ValueError("pathway_id is required when simulating from graph.")
        return self


class SimulateResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    result: SimulationResult
    warnings: tuple[ModelWarning, ...] = ()


class AnnotationGraphsResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    paper_ids: tuple[str, ...]


class PaperEvidenceGraphResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    graph: PaperEvidenceGraph


class PathwayProposalResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    proposal: PathwayProposal


class PredictOperatorsRequest(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    input: OperatorPredictionInput


class PredictOperatorsResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    prediction: OperatorPrediction
    warnings: tuple[ModelWarning, ...] = ()


class ApplyPredictionRequest(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    input: OperatorPredictionInput
    settings: SimulationSettings = Field(default_factory=SimulationSettings)
    parameter_overrides: dict[ParameterId, float] = Field(default_factory=dict)
    initial_condition_overrides: dict[StateId, float] = Field(default_factory=dict)
    allow_low_support: bool = False


class ApplyPredictionResponse(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    ok: Literal[True] = True
    prediction: OperatorPrediction
    graph: MoAGraph
    compiled_model: CompiledModel
    simulation: SimulationResult
    warnings: tuple[ModelWarning, ...] = ()


GraphPatchRequest = GraphComposeRequest
