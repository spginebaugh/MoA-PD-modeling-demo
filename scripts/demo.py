"""Generate reproducible demo outputs for the data-driven MoA PD prototype."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import cast

from services.domain import (
    CompiledModel,
    EquationTerm,
    ModifierTerm,
    OperatorPredictionInput,
    ParameterId,
    PathwayId,
    SimulationInput,
    SimulationResult,
    SimulationSettings,
    StateEquation,
    StateId,
    render_expression,
)
from services.equation_compiler.compiler import compile_graph
from services.pathway.composer import compose_graph
from services.pathway.loader import list_pathways, load_pathway
from services.pathway.models import GraphComposeRequest
from services.predictor.graph_patch import apply_edge_recommendations
from services.predictor.predict import predict_operator
from services.simulator.simulate import simulate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "demo_outputs"


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2))


def write_timeseries_csv(path: Path, response: SimulationResult) -> None:
    series = {item.state: item.values for item in response.series}
    states = [item.state for item in response.summaries]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["time", *[str(state) for state in states]])
        for idx, time in enumerate(response.time):
            writer.writerow([time, *[series[state][idx] for state in states]])


def _state_summaries(response: SimulationResult, states: tuple[StateId, ...]) -> dict[str, object]:
    by_state = {summary.state: summary for summary in response.summaries}
    return {str(state): by_state[state].model_dump(mode="json") for state in states if state in by_state}


def _first_falling_state(response: SimulationResult, states: tuple[StateId, ...]) -> dict[str, object] | None:
    summaries = {summary.state: summary for summary in response.summaries}
    candidates: list[tuple[StateId, float]] = []
    for state in states:
        summary = summaries.get(state)
        if summary is None or summary.time_to_10pct_drop_from_baseline is None:
            continue
        candidates.append((state, summary.time_to_10pct_drop_from_baseline))
    if not candidates:
        return None
    state, time_to_drop = min(candidates, key=lambda item: item[1])
    return {"state": str(state), "time_to_10pct_drop_from_baseline": time_to_drop}


def _parameter_values(response: SimulationResult, parameters: tuple[ParameterId, ...]) -> dict[str, float]:
    return {
        str(parameter): value for parameter, value in response.parameters.items() if parameter in parameters
    }


def _term_summary(term: EquationTerm) -> dict[str, object]:
    payload = term.model_dump(mode="json")
    payload["expression_text"] = render_expression(term.expression)
    return payload


def _modifier_summary(modifier: ModifierTerm) -> dict[str, object]:
    payload = modifier.model_dump(mode="json")
    payload["expression_text"] = render_expression(modifier.expression)
    return payload


def _equation_summary(equation: StateEquation) -> dict[str, object]:
    payload = equation.model_dump(mode="json")
    payload["expression_text"] = render_expression(equation.expression)
    return payload


def _compiled_focus(model: CompiledModel, states: tuple[StateId, ...]) -> dict[str, object]:
    state_set = set(states)
    return {
        "modifiers": [_modifier_summary(modifier) for modifier in model.modifiers],
        "terms": [_term_summary(term) for term in model.terms if term.state in state_set],
        "state_equations": [
            _equation_summary(equation) for equation in model.equations if equation.state in state_set
        ],
    }


def _hypothesis_edges(graph_model_dump: dict[str, object]) -> list[object]:
    edges = cast(list[dict[str, object]], graph_model_dump.get("edges", []))
    return [edge for edge in edges if edge.get("is_hypothesis") is True]


def _run_configuration(pathway_id: str, configuration: str) -> tuple[CompiledModel, SimulationResult]:
    graph = compose_graph(GraphComposeRequest(pathway_id=PathwayId(pathway_id), configuration=configuration))
    compiled = compile_graph(graph)
    response = simulate(
        SimulationInput(model=compiled, settings=SimulationSettings(dose=1.0, t_end=48, n_points=161))
    )
    return compiled, response


def _prediction_demo(pathway_id: str) -> dict[str, object]:
    pathway = load_pathway(pathway_id)
    if not pathway.prediction.training_cases:
        return {"ok": False, "message": "No prediction training cases configured."}
    claim = pathway.prediction.training_cases[-1].claim
    prediction, prediction_warnings = predict_operator(
        OperatorPredictionInput(pathway_id=PathwayId(pathway_id), claim_text=claim)
    )
    patched_graph = apply_edge_recommendations(
        None,
        prediction.recommendations,
        claim_text=claim,
        decision_source=prediction.diagnostics.decision_source,
        pathway_id=pathway_id,
        include_modules=prediction.diagnostics.included_modules,
    )
    patched_compiled = compile_graph(patched_graph)
    patched_response = simulate(
        SimulationInput(model=patched_compiled, settings=SimulationSettings(dose=1.0, t_end=48, n_points=161))
    )

    contrast_configuration = next(iter(pathway.configurations))
    direct_compiled, direct_response = _run_configuration(pathway_id, contrast_configuration)
    focus_states = patched_compiled.metadata.plot_states or patched_compiled.states
    focus_parameters = tuple(ParameterId(str(parameter)) for parameter in patched_response.parameters)
    graph_dump = patched_graph.model_dump(mode="json")
    return {
        "ok": True,
        "claim": claim,
        "prediction": prediction.model_dump(mode="json"),
        "warnings": [warning.model_dump(mode="json") for warning in prediction_warnings],
        "applied_patches": [patch.model_dump(mode="json") for patch in prediction.recommendations],
        "patched_graph": {
            "graph_id": str(patched_graph.graph_id),
            "label": patched_graph.label,
            "source_claim": patched_graph.source_claim,
            "edge_count": len(patched_graph.edges),
            "hypothesis_edges": _hypothesis_edges(graph_dump),
        },
        "compiled": _compiled_focus(patched_compiled, focus_states),
        "simulation": {
            "first_falling_state": _first_falling_state(patched_response, focus_states),
            "summaries": _state_summaries(patched_response, focus_states),
            "biological_logic": [
                logic.model_dump(mode="json") for logic in patched_response.biological_logic
            ],
            "parameter_values": _parameter_values(patched_response, focus_parameters),
        },
        "contrast": {
            "configuration": contrast_configuration,
            "first_falling_state": _first_falling_state(direct_response, focus_states),
            "modifiers": [_modifier_summary(modifier) for modifier in direct_compiled.modifiers],
            "summaries": _state_summaries(direct_response, focus_states),
            "biological_logic": [logic.model_dump(mode="json") for logic in direct_response.biological_logic],
        },
    }


def generate_demo_outputs(output_dir: Path, pathway_id: str | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    pathway_id = pathway_id or str(list_pathways()[0].pathway_id)
    pathway = load_pathway(pathway_id)
    comparison: dict[str, dict[str, object]] = {}
    for configuration in pathway.configurations:
        graph = compose_graph(
            GraphComposeRequest(pathway_id=PathwayId(pathway_id), configuration=configuration)
        )
        compiled = compile_graph(graph)
        response = simulate(
            SimulationInput(model=compiled, settings=SimulationSettings(dose=1.0, t_end=48, n_points=161))
        )
        write_json(output_dir / f"{configuration}_graph.json", graph.model_dump(mode="json"))
        write_json(output_dir / f"{configuration}_compiled_model.json", compiled.model_dump(mode="json"))
        write_json(output_dir / f"{configuration}_simulation.json", response.model_dump(mode="json"))
        write_timeseries_csv(output_dir / f"{configuration}_timecourse.csv", response)
        comparison[configuration] = {
            "modifiers": [modifier.model_dump(mode="json") for modifier in compiled.modifiers],
            "summaries": [summary.model_dump(mode="json") for summary in response.summaries],
            "biological_logic": [logic.model_dump(mode="json") for logic in response.biological_logic],
        }

    write_json(output_dir / "new_moa_claim_demo.json", _prediction_demo(pathway_id))
    write_json(output_dir / "comparison_summary.json", comparison)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="Directory for generated demo artifacts."
    )
    parser.add_argument(
        "--pathway",
        type=str,
        default=None,
        help="Pathway id to render. Defaults to the first loaded pathway.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    generate_demo_outputs(args.out, args.pathway)
    print(f"Wrote demo outputs to {args.out}")


if __name__ == "__main__":
    main()
