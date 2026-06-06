"""Public simulation orchestration for typed compiled MoA models."""

from __future__ import annotations

import numpy as np

from services.domain import ModelWarning, SimulationInput, SimulationResult, StateSeries

from .baseline import condition_dict, pre_equilibrate, seed_initial_conditions, set_state_value
from .biological_logic import biological_logic
from .metrics import control_normalized_series, series_by_state, series_tuple, state_summary
from .ode import solve_timecourse
from .validation import validate_simulation_ready


def simulate(simulation_input: SimulationInput) -> SimulationResult:
    compiled = simulation_input.model
    readiness_errors = validate_simulation_ready(compiled, simulation_input.parameter_overrides)
    if readiness_errors:
        messages = "; ".join(warning.message for warning in readiness_errors)
        raise ValueError(messages)

    params = compiled.parameter_catalog.values()
    params.update({key: float(value) for key, value in simulation_input.parameter_overrides.items()})

    seed_initials = seed_initial_conditions(simulation_input)
    baseline_y0, baseline_initials, baseline_diagnostics, baseline_warnings = pre_equilibrate(
        compiled,
        params,
        simulation_input.settings,
        seed_initials,
    )

    time = np.linspace(0.0, simulation_input.settings.t_end, simulation_input.settings.n_points)
    treated_y0 = np.array(baseline_y0, copy=True)
    set_state_value(compiled.states, treated_y0, compiled.metadata.drug_state, float(simulation_input.settings.dose))
    treated, treated_warnings = solve_timecourse(
        model=compiled,
        params=params,
        settings=simulation_input.settings,
        y0=treated_y0,
        time=time,
        exposure_dose=float(simulation_input.settings.dose),
        context="PD simulation",
    )

    control_series: tuple[StateSeries, ...] = ()
    control_normalized: tuple[StateSeries, ...] = ()
    control_warnings: tuple[ModelWarning, ...] = ()
    if simulation_input.settings.include_untreated_control:
        control_y0 = np.array(baseline_y0, copy=True)
        set_state_value(compiled.states, control_y0, compiled.metadata.drug_state, 0.0)
        control, control_warnings = solve_timecourse(
            model=compiled,
            params=params,
            settings=simulation_input.settings,
            y0=control_y0,
            time=time,
            exposure_dose=0.0,
            context="Untreated control simulation",
        )
        control_series = series_tuple(series_by_state(compiled, control))
        control_normalized = control_normalized_series(compiled, treated, control)

    treated_series_by_state = series_by_state(compiled, treated)
    summaries = {state: state_summary(state, time, values) for state, values in treated_series_by_state.items()}
    warnings = (*compiled.warnings, *baseline_warnings, *treated_warnings, *control_warnings)
    return SimulationResult(
        graph_id=compiled.graph_id,
        label=compiled.label,
        settings=simulation_input.settings,
        baseline_diagnostics=baseline_diagnostics,
        time=tuple(float(value) for value in time),
        series=series_tuple(treated_series_by_state),
        untreated_control_series=control_series,
        control_normalized_series=control_normalized,
        summaries=tuple(summaries.values()),
        biological_logic=biological_logic(compiled, summaries),
        parameters=params,
        seed_initial_conditions=seed_initials,
        baseline_initial_conditions=baseline_initials,
        initial_conditions=condition_dict(compiled.states, treated_y0),
        compiled_model=compiled,
        warnings=warnings,
    )
