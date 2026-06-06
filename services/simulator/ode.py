"""Graph-derived ODE evaluation and numerical solve helpers."""

from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from services.domain import (
    CompiledModel,
    DisplayExpression,
    ExposureMode,
    ModelWarning,
    ParameterId,
    SimulationSettings,
    WarningCategory,
    WarningSeverity,
    evaluate_expression,
)


def _warning(category: WarningCategory, message: str) -> ModelWarning:
    return ModelWarning(category=category, severity=WarningSeverity.WARNING, message=message)


def graph_derived_ode(
    t: float,
    y: np.ndarray,
    model: CompiledModel,
    params: dict[ParameterId, float],
    *,
    exposure_mode: ExposureMode,
    exposure_dose: float,
    force_drug_value: float | None = None,
) -> np.ndarray:
    del t
    values = np.maximum(y, 0.0)
    state_values = dict(zip(model.states, (float(value) for value in values), strict=True))
    drug_state = model.metadata.drug_state
    clamp_drug = drug_state is not None and (force_drug_value is not None or exposure_mode == ExposureMode.CONSTANT)
    if drug_state is not None and drug_state in state_values and clamp_drug:
        state_values[drug_state] = float(exposure_dose if force_drug_value is None else force_drug_value)
    equation_by_state = {equation.state: equation for equation in model.equations}
    derivatives: list[float] = []
    for state in model.states:
        if state == drug_state and clamp_drug:
            derivatives.append(0.0)
            continue
        expression = equation_by_state[state].expression
        if isinstance(expression, DisplayExpression):
            raise TypeError("Graph-derived simulation requires executable expression IR.")
        derivatives.append(evaluate_expression(expression, state_values, params))
    return np.asarray(derivatives, dtype=float)


def _solution_array(
    *,
    solution: object,
    state_count: int,
    fallback_columns: int,
    context: str,
    warnings: list[ModelWarning],
) -> np.ndarray:
    success = bool(getattr(solution, "success", False))
    message = str(getattr(solution, "message", "unknown solver failure"))
    if not success:
        warnings.append(_warning(WarningCategory.UNSTABLE_SIMULATION, f"{context} solver failure: {message}"))

    y = np.asarray(getattr(solution, "y", np.zeros((state_count, fallback_columns))), dtype=float)
    if y.ndim != 2 or y.shape[0] != state_count or y.shape[1] == 0:
        warnings.append(
            _warning(
                WarningCategory.UNSTABLE_SIMULATION,
                f"{context} returned an invalid state matrix; zeros were substituted.",
            )
        )
        y = np.zeros((state_count, fallback_columns), dtype=float)
    if not np.all(np.isfinite(y)):
        warnings.append(_warning(WarningCategory.UNSTABLE_SIMULATION, f"{context} produced non-finite values before clipping."))
    if np.nanmin(y) < -1e-7:
        warnings.append(_warning(WarningCategory.UNSTABLE_SIMULATION, f"{context} produced negative values; output was clipped at zero."))
    return np.clip(np.nan_to_num(y, nan=0.0, posinf=1e9, neginf=0.0), 0.0, None)


def _fit_time_columns(y: np.ndarray, expected_columns: int, context: str, warnings: list[ModelWarning]) -> np.ndarray:
    if y.shape[1] == expected_columns:
        return y
    warnings.append(
        _warning(
            WarningCategory.UNSTABLE_SIMULATION,
            f"{context} returned {y.shape[1]} time columns for {expected_columns} requested samples.",
        )
    )
    if y.shape[1] == 1:
        return np.repeat(y, expected_columns, axis=1)
    old_x = np.linspace(0.0, 1.0, y.shape[1])
    new_x = np.linspace(0.0, 1.0, expected_columns)
    return np.asarray([np.interp(new_x, old_x, row) for row in y], dtype=float)


def solve_timecourse(
    *,
    model: CompiledModel,
    params: dict[ParameterId, float],
    settings: SimulationSettings,
    y0: np.ndarray,
    time: np.ndarray,
    exposure_dose: float,
    context: str,
) -> tuple[np.ndarray, tuple[ModelWarning, ...]]:
    warnings: list[ModelWarning] = []
    solution = solve_ivp(
        fun=lambda t, y: graph_derived_ode(
            t,
            y,
            model,
            params,
            exposure_mode=settings.exposure_mode,
            exposure_dose=exposure_dose,
        ),
        t_span=(0.0, settings.t_end),
        y0=y0,
        t_eval=time,
        rtol=1e-6,
        atol=1e-9,
        max_step=max(settings.t_end / max(settings.n_points - 1, 1), 0.05),
    )
    y = _solution_array(
        solution=solution,
        state_count=len(model.states),
        fallback_columns=len(time),
        context=context,
        warnings=warnings,
    )
    return _fit_time_columns(y, len(time), context, warnings), tuple(warnings)


def solve_no_drug_baseline(
    *,
    model: CompiledModel,
    params: dict[ParameterId, float],
    settings: SimulationSettings,
    y0: np.ndarray,
) -> tuple[np.ndarray, tuple[ModelWarning, ...]]:
    warnings: list[ModelWarning] = []
    solution = solve_ivp(
        fun=lambda t, y: graph_derived_ode(
            t,
            y,
            model,
            params,
            exposure_mode=ExposureMode.CONSTANT,
            exposure_dose=0.0,
            force_drug_value=0.0,
        ),
        t_span=(0.0, settings.baseline_t_end),
        y0=y0,
        rtol=1e-7,
        atol=1e-10,
        max_step=max(settings.baseline_t_end / 400.0, 0.05),
    )
    y = _solution_array(
        solution=solution,
        state_count=len(model.states),
        fallback_columns=1,
        context="Baseline pre-equilibration",
        warnings=warnings,
    )
    return y, tuple(warnings)
