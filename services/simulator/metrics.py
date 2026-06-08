"""Simulation time-course metrics and series conversion."""

from __future__ import annotations

import numpy as np

from services.domain import CompiledModel, StateId, StateSeries, StateSummary

EPSILON = 1e-12


def _fraction_change(value: float, baseline: float) -> float | None:
    if abs(baseline) <= EPSILON:
        return None
    return float((value - baseline) / baseline)


def _drop_fraction(minimum: float, baseline: float) -> float | None:
    if abs(baseline) <= EPSILON:
        return None
    return float(max((baseline - minimum) / baseline, 0.0))


def _rise_fraction(maximum: float, baseline: float) -> float | None:
    if abs(baseline) <= EPSILON:
        return None
    return float(max((maximum - baseline) / baseline, 0.0))


def _time_to_fraction_drop(
    time: np.ndarray, values: np.ndarray, baseline: float, fraction: float
) -> float | None:
    if values.size == 0 or abs(baseline) <= EPSILON:
        return None
    threshold = baseline * (1.0 - fraction)
    hits = np.where(values <= threshold)[0]
    if hits.size == 0:
        return None
    return float(time[int(hits[0])])


def state_summary(state: StateId, time: np.ndarray, values: tuple[float, ...]) -> StateSummary:
    arr = np.asarray(values, dtype=float)
    baseline = float(arr[0])
    final = float(arr[-1])
    minimum_index = int(np.argmin(arr))
    maximum_index = int(np.argmax(arr))
    minimum = float(arr[minimum_index])
    maximum = float(arr[maximum_index])
    delta = arr - baseline
    below = np.maximum(-delta, 0.0)
    above = np.maximum(delta, 0.0)
    return StateSummary(
        state=state,
        baseline=baseline,
        final=final,
        minimum=minimum,
        maximum=maximum,
        final_fraction_change_from_baseline=_fraction_change(final, baseline),
        max_drop_fraction_from_baseline=_drop_fraction(minimum, baseline),
        time_to_nadir=float(time[minimum_index]),
        max_rise_fraction_from_baseline=_rise_fraction(maximum, baseline),
        time_to_peak=float(time[maximum_index]),
        auc=float(np.trapezoid(arr, time)),
        auc_change_from_baseline=float(np.trapezoid(delta, time)),
        auc_below_baseline=float(np.trapezoid(below, time)),
        auc_above_baseline=float(np.trapezoid(above, time)),
        time_to_10pct_drop_from_baseline=_time_to_fraction_drop(time, arr, baseline, fraction=0.10),
        time_to_20pct_drop_from_baseline=_time_to_fraction_drop(time, arr, baseline, fraction=0.20),
    )


def series_by_state(model: CompiledModel, y: np.ndarray) -> dict[StateId, tuple[float, ...]]:
    return {state: tuple(float(value) for value in y[index, :]) for index, state in enumerate(model.states)}


def series_tuple(series_by_state: dict[StateId, tuple[float, ...]]) -> tuple[StateSeries, ...]:
    return tuple(StateSeries(state=state, values=values) for state, values in series_by_state.items())


def control_normalized_series(
    model: CompiledModel, treated: np.ndarray, control: np.ndarray
) -> tuple[StateSeries, ...]:
    normalized: list[StateSeries] = []
    plot_states = set(model.metadata.plot_states or model.states)
    for index, state in enumerate(model.states):
        if state not in plot_states:
            continue
        denominator = control[index, :]
        if np.any(np.abs(denominator) <= EPSILON):
            continue
        ratio = np.clip(np.nan_to_num(treated[index, :] / denominator, nan=0.0, posinf=1e9), 0.0, None)
        normalized.append(StateSeries(state=state, values=tuple(float(value) for value in ratio)))
    return tuple(normalized)
