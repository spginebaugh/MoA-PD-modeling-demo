"""No-drug baseline initialization for graph-derived PD simulation."""

from __future__ import annotations

import numpy as np

from services.domain import (
    BaselineDiagnostics,
    BaselineMode,
    CompiledModel,
    ExposureMode,
    ModelWarning,
    ParameterId,
    SimulationInput,
    SimulationSettings,
    StateId,
    WarningCategory,
    WarningSeverity,
)

from .metrics import EPSILON
from .ode import graph_derived_ode, solve_no_drug_baseline


def _warning(category: WarningCategory, message: str) -> ModelWarning:
    return ModelWarning(category=category, severity=WarningSeverity.WARNING, message=message)


def seed_initial_conditions(simulation_input: SimulationInput) -> dict[StateId, float]:
    initials = dict(simulation_input.model.metadata.initial_conditions)
    initials.update({state: float(value) for state, value in simulation_input.initial_condition_overrides.items()})
    drug_state = simulation_input.model.metadata.drug_state
    if drug_state is not None and drug_state in initials:
        initials[drug_state] = 0.0
    return {state: max(float(initials[state]), 0.0) for state in simulation_input.model.states}


def set_state_value(states: tuple[StateId, ...], values: np.ndarray, state: StateId | None, value: float) -> None:
    if state is not None and state in states:
        values[states.index(state)] = value


def condition_dict(states: tuple[StateId, ...], values: np.ndarray) -> dict[StateId, float]:
    return {state: float(values[index]) for index, state in enumerate(states)}


def pre_equilibrate(
    model: CompiledModel,
    params: dict[ParameterId, float],
    settings: SimulationSettings,
    seed_initials: dict[StateId, float],
) -> tuple[np.ndarray, dict[StateId, float], BaselineDiagnostics, tuple[ModelWarning, ...]]:
    if settings.baseline_mode != BaselineMode.PRE_EQUILIBRATED:
        raise ValueError(f"Unsupported baseline mode: {settings.baseline_mode}")

    y0 = np.asarray([seed_initials[state] for state in model.states], dtype=float)
    y, solver_warnings = solve_no_drug_baseline(model=model, params=params, settings=settings, y0=y0)
    warnings = list(solver_warnings)
    baseline = np.asarray(y[:, -1], dtype=float)
    set_state_value(model.states, baseline, model.metadata.drug_state, 0.0)

    derivative = graph_derived_ode(
        settings.baseline_t_end,
        baseline,
        model,
        params,
        exposure_mode=ExposureMode.CONSTANT,
        exposure_dose=0.0,
        force_drug_value=0.0,
    )
    drug_state = model.metadata.drug_state
    non_drug_indices = [index for index, state in enumerate(model.states) if state != drug_state]
    derivative_slice = derivative[non_drug_indices] if non_drug_indices else derivative
    seed_slice = y0[non_drug_indices] if non_drug_indices else y0
    baseline_slice = baseline[non_drug_indices] if non_drug_indices else baseline
    max_abs_derivative = float(np.max(np.abs(derivative_slice))) if derivative_slice.size else 0.0
    max_abs_fraction_change = (
        float(np.max(np.abs(baseline_slice - seed_slice) / np.maximum(np.abs(seed_slice), EPSILON)))
        if seed_slice.size
        else 0.0
    )
    diagnostics = BaselineDiagnostics(
        mode=BaselineMode.PRE_EQUILIBRATED,
        t_end=float(settings.baseline_t_end),
        tolerance=float(settings.baseline_tolerance),
        converged=bool(max_abs_derivative <= settings.baseline_tolerance),
        max_abs_derivative=max_abs_derivative,
        max_abs_fraction_change_from_seed=max_abs_fraction_change,
    )
    if not diagnostics.converged:
        warnings.append(
            _warning(
                WarningCategory.UNSTABLE_SIMULATION,
                "No-drug pre-equilibration did not reach the requested derivative tolerance "
                f"({max_abs_derivative:.3g} > {settings.baseline_tolerance:.3g}).",
            )
        )
    return baseline, condition_dict(model.states, baseline), diagnostics, tuple(warnings)
