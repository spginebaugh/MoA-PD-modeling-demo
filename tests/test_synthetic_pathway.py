from __future__ import annotations

from services.domain import InitialConditions, MoAGraph, PathwayId, SimulationInput, SimulationSettings
from services.equation_compiler.compiler import compile_graph
from services.pathway.models import ParameterBlock, PathwayDefinition
from services.simulator.simulate import simulate


def test_minimal_non_egfr_pathway_compiles_and_simulates() -> None:
    pathway_id = PathwayId("toy_pathway")
    graph = MoAGraph.model_validate(
        {
            "graph_id": "toy_graph",
            "label": "Toy graph",
            "context": {"species": "synthetic"},
            "nodes": [
                {
                    "id": "Drug",
                    "label": "Input compound",
                    "type": "perturbation",
                    "roles": ["drug"],
                    "state": {"id": "Drug", "executable": True, "initial": 0.0},
                },
                {
                    "id": "Input",
                    "label": "Input",
                    "type": "signal",
                    "state": {"id": "Input", "executable": True, "initial": 1.0},
                },
                {
                    "id": "Output",
                    "label": "Output",
                    "type": "readout",
                    "state": {"id": "Output", "executable": True, "initial": 0.2},
                },
            ],
            "edges": [
                {
                    "id": "e_input_to_output",
                    "source": "Input",
                    "target": "Output",
                    "relation": "activates",
                    "operator": "activation",
                    "sign": "+",
                    "evidence": [{"description": "Synthetic activation edge."}],
                }
            ],
            "metadata": {"pathway_id": pathway_id, "drug_state": "Drug", "endpoint_states": ["Output"]},
        }
    )
    pathway = PathwayDefinition.model_validate(
        {
            "pathway_id": pathway_id,
            "label": "Toy pathway",
            "context": {"species": "synthetic"},
            "base_graph": {
                "graph_id": "toy_base",
                "label": "Toy base",
                "nodes": graph.nodes,
                "edges": graph.edges,
            },
            "parameters": ParameterBlock.model_validate(
                {
                    "priors": {
                        "kel": {"id": "kel", "value": 0.1},
                        "k_Input_to_Output": {"id": "k_Input_to_Output", "value": 0.3},
                        "K_Input": {"id": "K_Input", "value": 0.5},
                        "k_output_loss": {"id": "k_output_loss", "value": 0.05},
                    }
                }
            ),
            "initial_conditions": InitialConditions.model_validate(
                {"values": {"Drug": 0.0, "Input": 1.0, "Output": 0.2}}
            ),
            "homeostasis": [
                {
                    "state": "Drug",
                    "term_id": "term_drug_loss",
                    "operator": "pk_elimination",
                    "sign": "-",
                    "description": "Drug loss.",
                    "expression": {"kind": "first_order_loss", "state": "Drug", "rate": "kel"},
                },
                {
                    "state": "Output",
                    "term_id": "term_output_loss",
                    "operator": "first_order_loss",
                    "sign": "-",
                    "description": "Output loss.",
                    "expression": {"kind": "first_order_loss", "state": "Output", "rate": "k_output_loss"},
                },
            ],
        }
    )

    compiled = compile_graph(graph, pathway)
    result = simulate(SimulationInput(model=compiled, settings=SimulationSettings(t_end=4, n_points=9)))

    assert tuple(str(state) for state in compiled.states) == ("Drug", "Input", "Output")
    assert len(result.series) == 3
    assert result.summaries[-1].state == "Output"
