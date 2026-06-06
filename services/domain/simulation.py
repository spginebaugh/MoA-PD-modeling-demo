"""Typed simulation domain models."""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from .base import STRICT_MODEL_CONFIG
from .compiled_model import CompiledModel
from .identifiers import EdgeId, GraphId, ParameterId, StateId
from .warnings import ModelWarning


class BaselineMode(StrEnum):
    PRE_EQUILIBRATED = "pre_equilibrated"


class ExposureMode(StrEnum):
    CONSTANT = "constant"
    BOLUS = "bolus"


class SimulationSettings(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    dose: float = Field(default=1.0, ge=0.0)
    t_end: float = Field(default=48.0, gt=0.0)
    n_points: int = Field(default=161, ge=2, le=5000)
    baseline_mode: BaselineMode = BaselineMode.PRE_EQUILIBRATED
    baseline_t_end: float = Field(default=168.0, gt=0.0)
    baseline_tolerance: float = Field(default=2e-4, gt=0.0)
    exposure_mode: ExposureMode = ExposureMode.BOLUS
    include_untreated_control: bool = True

    @field_validator("dose", "t_end", "baseline_t_end", "baseline_tolerance")
    @classmethod
    def settings_values_are_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Simulation setting values must be finite")
        return value


class SimulationInput(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    model: CompiledModel
    settings: SimulationSettings = Field(default_factory=SimulationSettings)
    parameter_overrides: dict[ParameterId, float] = Field(default_factory=dict)
    initial_condition_overrides: dict[StateId, float] = Field(default_factory=dict)

    @field_validator("parameter_overrides")
    @classmethod
    def parameter_overrides_are_finite(cls, values: dict[ParameterId, float]) -> dict[ParameterId, float]:
        for parameter_id, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"Parameter override {parameter_id} must be finite")
            if value < 0.0:
                raise ValueError(f"Parameter override {parameter_id} must be non-negative")
        return values

    @field_validator("initial_condition_overrides")
    @classmethod
    def initial_overrides_are_finite_nonnegative(cls, values: dict[StateId, float]) -> dict[StateId, float]:
        for state, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"Initial-condition override {state} must be finite")
            if value < 0.0:
                raise ValueError(f"Initial-condition override {state} must be non-negative")
        return values

    @model_validator(mode="after")
    def overrides_reference_known_values(self) -> SimulationInput:
        known_parameters = self.model.parameter_catalog.known_parameter_ids()
        unknown_parameters = [
            parameter for parameter in self.parameter_overrides if parameter not in known_parameters
        ]
        if unknown_parameters:
            raise ValueError(f"Unknown parameter overrides: {unknown_parameters}")
        unknown_states = [state for state in self.initial_condition_overrides if state not in self.model.states]
        if unknown_states:
            raise ValueError(f"Unknown initial-condition overrides: {unknown_states}")
        return self


class StateSeries(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    state: StateId
    values: tuple[float, ...]

    @field_validator("values")
    @classmethod
    def values_are_finite_nonnegative(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        for value in values:
            if not math.isfinite(value):
                raise ValueError("State series values must be finite")
            if value < 0.0:
                raise ValueError("State series values must be non-negative")
        return values


class BaselineDiagnostics(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    mode: BaselineMode
    t_end: float
    tolerance: float
    converged: bool
    max_abs_derivative: float
    max_abs_fraction_change_from_seed: float

    @field_validator("t_end", "tolerance", "max_abs_derivative", "max_abs_fraction_change_from_seed")
    @classmethod
    def diagnostics_values_are_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Baseline diagnostics values must be finite")
        if value < 0.0:
            raise ValueError("Baseline diagnostics values must be non-negative")
        return value


class StateSummary(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    state: StateId
    baseline: float
    final: float
    minimum: float
    maximum: float
    final_fraction_change_from_baseline: float | None
    max_drop_fraction_from_baseline: float | None
    time_to_nadir: float
    max_rise_fraction_from_baseline: float | None
    time_to_peak: float
    auc: float
    auc_change_from_baseline: float
    auc_below_baseline: float
    auc_above_baseline: float
    time_to_10pct_drop_from_baseline: float | None
    time_to_20pct_drop_from_baseline: float | None

    @field_validator(
        "baseline",
        "final",
        "minimum",
        "maximum",
        "final_fraction_change_from_baseline",
        "max_drop_fraction_from_baseline",
        "time_to_nadir",
        "max_rise_fraction_from_baseline",
        "time_to_peak",
        "auc",
        "auc_change_from_baseline",
        "auc_below_baseline",
        "auc_above_baseline",
        "time_to_10pct_drop_from_baseline",
        "time_to_20pct_drop_from_baseline",
    )
    @classmethod
    def summary_values_are_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("State summary values must be finite")
        return value


class BiologicalLogicCheck(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    result: bool | None
    rationale: str = Field(min_length=1)
    source_states: tuple[StateId, ...]
    source_edges: tuple[EdgeId, ...] = ()


class SimulationResult(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    graph_id: GraphId
    label: str = Field(min_length=1)
    settings: SimulationSettings
    baseline_diagnostics: BaselineDiagnostics
    time: tuple[float, ...]
    series: tuple[StateSeries, ...]
    untreated_control_series: tuple[StateSeries, ...] = ()
    control_normalized_series: tuple[StateSeries, ...] = ()
    summaries: tuple[StateSummary, ...]
    biological_logic: tuple[BiologicalLogicCheck, ...]
    parameters: dict[ParameterId, float]
    seed_initial_conditions: dict[StateId, float]
    baseline_initial_conditions: dict[StateId, float]
    initial_conditions: dict[StateId, float]
    compiled_model: CompiledModel
    warnings: tuple[ModelWarning, ...] = ()

    @model_validator(mode="after")
    def series_lengths_match_time(self) -> SimulationResult:
        for value in self.time:
            if not math.isfinite(value):
                raise ValueError("Simulation time values must be finite")
            if value < 0.0:
                raise ValueError("Simulation time values must be non-negative")
        if len(set(self.time)) != len(self.time):
            raise ValueError("Simulation time values must be unique")
        if tuple(sorted(self.time)) != self.time:
            raise ValueError("Simulation time values must be monotonic increasing")
        expected = len(self.time)
        for label, items in (
            ("state", self.series),
            ("untreated control", self.untreated_control_series),
            ("control-normalized", self.control_normalized_series),
        ):
            states = [series.state for series in items]
            if len(states) != len(set(states)):
                raise ValueError(f"Simulation result contains duplicate {label} series")
            bad_lengths = [str(series.state) for series in items if len(series.values) != expected]
            if bad_lengths:
                raise ValueError(f"{label.title()} series length does not match time vector for states: {bad_lengths}")
        summary_states = [summary.state for summary in self.summaries]
        if len(summary_states) != len(set(summary_states)):
            raise ValueError("Simulation result contains duplicate state summaries")
        for parameter_id, value in self.parameters.items():
            if not math.isfinite(value):
                raise ValueError(f"Simulation parameter {parameter_id} must be finite")
        for label, conditions in (
            ("seed initial", self.seed_initial_conditions),
            ("baseline initial", self.baseline_initial_conditions),
            ("simulation initial", self.initial_conditions),
        ):
            for state, value in conditions.items():
                if not math.isfinite(value):
                    raise ValueError(f"{label.title()} condition {state} must be finite")
                if value < 0.0:
                    raise ValueError(f"{label.title()} condition {state} must be non-negative")
        return self
