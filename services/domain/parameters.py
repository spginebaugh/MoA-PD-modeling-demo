"""Parameter prior and initial-condition domain."""

from __future__ import annotations

import fnmatch
import math

from pydantic import BaseModel, Field, field_validator, model_validator

from .base import STRICT_MODEL_CONFIG
from .graph import Evidence
from .identifiers import EdgeId, OperatorId, ParameterId, StateId


class ParameterPrior(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: ParameterId
    value: float
    lower: float | None = None
    upper: float | None = None
    units: str | None = None
    source: Evidence | None = None

    @field_validator("value", "lower", "upper")
    @classmethod
    def finite_numbers(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Parameter prior values must be finite")
        if value is not None and value < 0.0:
            raise ValueError("Parameter prior values must be non-negative")
        return value

    @model_validator(mode="after")
    def bounds_contain_value(self) -> ParameterPrior:
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError(f"Parameter {self.id} has lower bound greater than upper bound")
        if self.lower is not None and self.value < self.lower:
            raise ValueError(f"Parameter {self.id} value is below lower bound")
        if self.upper is not None and self.value > self.upper:
            raise ValueError(f"Parameter {self.id} value is above upper bound")
        return self


class GeneratedParameter(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: ParameterId
    source_edges: tuple[EdgeId, ...] = ()
    operator: OperatorId | None = None
    units: str | None = None
    has_prior: bool = False
    required_for_execution: bool = True
    default_value: float | None = None

    @field_validator("default_value")
    @classmethod
    def finite_default(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value < 0.0):
            raise ValueError("Generated parameter default_value must be finite and non-negative")
        return value


class ParameterCatalog(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    priors: dict[ParameterId, ParameterPrior]
    generated: dict[ParameterId, GeneratedParameter] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ids_match_keys(self) -> ParameterCatalog:
        for key, prior in self.priors.items():
            if prior.id != key:
                raise ValueError(f"Parameter prior key {key!r} does not match id {prior.id!r}")
        for key, generated in self.generated.items():
            if generated.id != key:
                raise ValueError(f"Generated parameter key {key!r} does not match id {generated.id!r}")
            if key in self.priors:
                raise ValueError(f"Generated parameter {key!r} collides with a prior parameter")
        return self

    def known_parameter_ids(self) -> frozenset[ParameterId]:
        return frozenset(self.priors) | frozenset(self.generated)

    def values(self) -> dict[ParameterId, float]:
        values = {parameter_id: prior.value for parameter_id, prior in self.priors.items()}
        values.update(
            {
                parameter_id: generated.default_value
                for parameter_id, generated in self.generated.items()
                if generated.default_value is not None
            }
        )
        return values

    def with_generated(self, generated_parameters: tuple[GeneratedParameter, ...]) -> ParameterCatalog:
        generated = dict(self.generated)
        for parameter in generated_parameters:
            if parameter.id not in self.priors:
                generated[parameter.id] = parameter
        return self.model_copy(update={"generated": generated})


class InitialConditions(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    values: dict[StateId, float]

    @field_validator("values")
    @classmethod
    def finite_nonnegative_values(cls, values: dict[StateId, float]) -> dict[StateId, float]:
        for state, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"Initial condition for {state} must be finite")
            if value < 0.0:
                raise ValueError(f"Initial condition for {state} must be non-negative")
        return values


class GeneratedParameterDefaults(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    patterns: dict[str, float] = Field(default_factory=dict)

    @field_validator("patterns")
    @classmethod
    def finite_nonnegative_values(cls, values: dict[str, float]) -> dict[str, float]:
        for pattern, value in values.items():
            if not pattern:
                raise ValueError("Generated parameter default pattern must be non-empty")
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"Generated parameter default for {pattern!r} must be finite and non-negative")
        return values

    def value_for(self, parameter: ParameterId) -> float | None:
        text = str(parameter)
        for pattern, value in self.patterns.items():
            if fnmatch.fnmatchcase(text, pattern):
                return value
        return None
