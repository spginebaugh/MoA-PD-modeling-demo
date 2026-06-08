"""Data-defined biological logic checks."""

from __future__ import annotations

from collections.abc import Mapping

from services.domain import BiologicalLogicCheck, CompiledModel, EdgeId, StateId, StateSummary
from services.domain.base import JsonValue


def _summary(summaries: dict[StateId, StateSummary], state: JsonValue) -> StateSummary | None:
    if not isinstance(state, str):
        return None
    return summaries.get(StateId(state))


def _number(value: JsonValue, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def _drop_before(check: Mapping[str, JsonValue], summaries: dict[StateId, StateSummary]) -> bool | None:
    upstream = _summary(summaries, check.get("upstream_state"))
    downstream = _summary(summaries, check.get("downstream_state"))
    if upstream is None or downstream is None:
        return None
    fraction = _number(check.get("fraction"), 0.1)
    up_time = (
        upstream.time_to_10pct_drop_from_baseline
        if fraction <= 0.1
        else upstream.time_to_20pct_drop_from_baseline
    )
    down_time = (
        downstream.time_to_10pct_drop_from_baseline
        if fraction <= 0.1
        else downstream.time_to_20pct_drop_from_baseline
    )
    if up_time is None or down_time is None:
        return None
    return up_time < down_time


def _drop_at_least(check: Mapping[str, JsonValue], summaries: dict[StateId, StateSummary]) -> bool | None:
    summary = _summary(summaries, check.get("state"))
    if summary is None or summary.max_drop_fraction_from_baseline is None:
        return None
    return summary.max_drop_fraction_from_baseline >= _number(check.get("fraction"), 0.1)


def _preserved(check: Mapping[str, JsonValue], summaries: dict[StateId, StateSummary]) -> bool | None:
    summary = _summary(summaries, check.get("state"))
    if summary is None or summary.max_drop_fraction_from_baseline is None:
        return None
    return summary.max_drop_fraction_from_baseline <= _number(check.get("max_drop"), 0.05)


def _check_result(check: Mapping[str, JsonValue], summaries: dict[StateId, StateSummary]) -> bool | None:
    kind = check.get("kind")
    if kind == "drop_before":
        return _drop_before(check, summaries)
    if kind == "drop_at_least":
        return _drop_at_least(check, summaries)
    if kind == "preserved":
        return _preserved(check, summaries)
    return None


def _source_states(check: Mapping[str, JsonValue]) -> tuple[StateId, ...]:
    values: list[StateId] = []
    for key in ("state", "upstream_state", "downstream_state"):
        value = check.get(key)
        if isinstance(value, str):
            values.append(StateId(value))
    return tuple(dict.fromkeys(values))


def _source_edges(raw: JsonValue) -> tuple[EdgeId, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(EdgeId(edge) for edge in raw if isinstance(edge, str))


def biological_logic(
    compiled: CompiledModel,
    summaries: dict[StateId, StateSummary],
) -> tuple[BiologicalLogicCheck, ...]:
    results: list[BiologicalLogicCheck] = []
    for raw in compiled.metadata.logic_checks:
        check = raw.get("check")
        if not isinstance(check, dict):
            continue
        label = raw.get("label", raw.get("id", "Logic check"))
        rationale = raw.get("rationale", "Data-defined pathway logic check.")
        results.append(
            BiologicalLogicCheck(
                id=str(raw.get("id", "logic_check")),
                label=str(label),
                result=_check_result(check, summaries),
                rationale=str(rationale),
                source_states=_source_states(check),
                source_edges=_source_edges(raw.get("source_edges")),
            )
        )
    return tuple(results)
