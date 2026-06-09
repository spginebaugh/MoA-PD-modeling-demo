from __future__ import annotations

import math

from services.domain import (
    EdgeId,
    ModuleId,
    OperatorPredictionInput,
    PathwayId,
    RelationId,
    SimulationInput,
    SimulationSettings,
    StateId,
)
from services.equation_compiler.compiler import compile_graph
from services.pathway.composer import compose_graph
from services.pathway.loader import list_pathways, load_pathway
from services.pathway.models import AdHocEdgeModifier, GraphComposeRequest
from services.predictor.graph_patch import apply_edge_recommendations
from services.predictor.predict import predict_operator
from services.simulator.simulate import simulate

PATHWAY = PathwayId("egfr_erbb_demo")
PATHWAY_ID = str(PATHWAY)


def test_pathway_definition_loads_from_single_source_of_truth() -> None:
    pathway = load_pathway(PATHWAY_ID)

    assert pathway.pathway_id == PATHWAY_ID
    assert {summary.pathway_id for summary in list_pathways()} == {
        PATHWAY_ID,
        "sunitinib_vegfr2_hcc_demo",
    }
    assert "cbl_turnover" in pathway.modules
    assert "direct_kinase_inhibition" in pathway.configurations
    assert "cbl_degradation" in pathway.configurations


def test_module_composition_includes_and_excludes_cbl_pathway_elements() -> None:
    base = compose_graph(GraphComposeRequest(pathway_id=PATHWAY, configuration="base_signaling"))
    with_module = compose_graph(GraphComposeRequest(pathway_id=PATHWAY, configuration="cbl_module_only"))

    assert "cbl_turnover" not in base.metadata.included_modules
    assert "CBL_active" not in {str(node.id) for node in base.nodes}
    assert "e_cbl_ubiquitinates_egfr" not in {str(edge.id) for edge in base.edges}

    assert "cbl_turnover" in with_module.metadata.included_modules
    assert "CBL_active" in {str(node.id) for node in with_module.nodes}
    assert "e_cbl_ubiquitinates_egfr" in {str(edge.id) for edge in with_module.edges}


def test_configurations_compile_to_distinct_graph_modifier_signatures() -> None:
    signatures: dict[str, tuple[tuple[str, str], ...]] = {}
    for configuration in (
        "direct_kinase_inhibition",
        "ligand_blockade",
        "downstream_pathway_blockade",
        "cbl_degradation",
    ):
        graph = compose_graph(GraphComposeRequest(pathway_id=PATHWAY, configuration=configuration))
        compiled = compile_graph(graph)
        signatures[configuration] = tuple(
            sorted((str(modifier.target_edge), str(modifier.operator)) for modifier in compiled.modifiers)
        )
        assert compiled.metadata.pathway_id == PATHWAY_ID
        assert compiled.metadata.expressions_execute_directly is True
        assert not [warning for warning in compiled.warnings if warning.severity == "error"]

    assert len(set(signatures.values())) == len(signatures)


def test_ad_hoc_modifier_can_target_any_present_structural_edge() -> None:
    graph = compose_graph(
        GraphComposeRequest(
            pathway_id=PATHWAY,
            include_modules=(ModuleId("cbl_turnover"),),
            ad_hoc_modifiers=(
                AdHocEdgeModifier(
                    target_edge=EdgeId("e_pegfr_activates_cbl"),
                    relation=RelationId("activates_edge"),
                ),
            ),
        )
    )
    compiled = compile_graph(graph)

    assert "e_pegfr_activates_cbl" in {str(edge.id) for edge in graph.structural_edges()}
    assert any(str(modifier.target_edge) == "e_pegfr_activates_cbl" for modifier in compiled.modifiers)
    generated_values = compiled.parameter_catalog.values()
    assert generated_values[compiled.modifiers[0].parameters[0]] >= 0.0


def test_simulation_uses_dynamic_states_and_data_defined_logic_checks() -> None:
    graph = compose_graph(GraphComposeRequest(pathway_id=PATHWAY, configuration="cbl_degradation"))
    compiled = compile_graph(graph)
    result = simulate(SimulationInput(model=compiled, settings=SimulationSettings(t_end=24, n_points=61)))

    assert {series.state for series in result.series} == set(compiled.states)
    assert all(math.isfinite(value) and value >= 0.0 for series in result.series for value in series.values)
    logic = {item.id: item for item in result.biological_logic}
    assert logic["total_receptor_falls_before_downstream_signal"].result is True
    summaries = {summary.state: summary for summary in result.summaries}
    assert summaries[StateId("EGFR_total")].time_to_10pct_drop_from_baseline is not None


def test_prediction_can_include_module_then_target_edges_inside_it() -> None:
    claim = "Compound promotes CBL-mediated EGFR degradation rather than directly inhibiting kinase activity."
    prediction, warnings = predict_operator(OperatorPredictionInput(pathway_id=PATHWAY, claim_text=claim))

    assert warnings
    assert prediction.diagnostics.decision_source == "guardrail"
    assert prediction.diagnostics.included_modules == ("cbl_turnover",)
    assert {str(item.target) for item in prediction.recommendations} == {
        "e_cbl_ubiquitinates_egfr",
        "e_ubiquitinated_egfr_degrades_total",
    }

    patched = apply_edge_recommendations(
        None,
        prediction.recommendations,
        claim_text=claim,
        decision_source=prediction.diagnostics.decision_source,
        pathway_id=PATHWAY_ID,
        include_modules=prediction.diagnostics.included_modules,
    )
    assert "cbl_turnover" in patched.metadata.included_modules
    assert len(patched.modifier_edges()) == 2


def test_prediction_abstains_when_claim_has_no_supported_graph_patch() -> None:
    prediction, warnings = predict_operator(
        OperatorPredictionInput(
            pathway_id=PATHWAY,
            claim_text="Compound promotes receptor degradation.",
        )
    )

    assert warnings
    assert prediction.diagnostics.decision_source == "abstain"
    assert prediction.diagnostics.low_support is True
    assert not any(
        feature.startswith("training_positive:")
        for feature in prediction.diagnostics.matched_positive_features
    )
