from __future__ import annotations

import math

from services.domain import DisplayExpression, PathwayId, SimulationInput, SimulationSettings, StateId
from services.equation_compiler.compiler import compile_graph
from services.pathway.composer import compose_graph
from services.pathway.loader import list_pathways, load_pathway
from services.pathway.models import GraphComposeRequest
from services.simulator.simulate import simulate

PATHWAY_ID = "sunitinib_vegfr2_hcc_demo"
PAPER_ID = "PMC5131886"
CONFIGURATION = "normalized_executable_slice"
RUNTIME_STATES = {
    StateId("ActiveExposure"),
    StateId("sVEGFR2"),
    StateId("DeltaSVEGFR2"),
    StateId("TumorGrowthRate"),
    StateId("TumorVolume"),
}


def _compose_demo_graph():
    return compose_graph(
        GraphComposeRequest(pathway_id=PathwayId(PATHWAY_ID), configuration=CONFIGURATION)
    )


def test_sunitinib_paper_pathway_loads_with_context_parameters_and_state_bindings() -> None:
    pathway = load_pathway(PATHWAY_ID)

    assert pathway.pathway_id == PATHWAY_ID
    assert PATHWAY_ID in {summary.pathway_id for summary in list_pathways()}
    assert pathway.context.species == "human"
    assert pathway.context.endpoint == "TumorVolume"
    assert pathway.context.extension["paper_id"] == PAPER_ID
    assert pathway.context.extension["disease"] == "HCC"
    assert pathway.context.extension["translation_stage"] == "clinical"
    assert CONFIGURATION in pathway.configurations
    assert set(pathway.initial_conditions.values) == RUNTIME_STATES
    assert {node.state.id for node in pathway.base_graph.nodes if node.state is not None} == RUNTIME_STATES
    assert tuple(pathway.presentation.endpoint_states) == (StateId("TumorVolume"),)

    for parameter in pathway.parameters.priors.values():
        assert parameter.source is not None
        assert parameter.source.source_type == "expert_review"
        assert parameter.source.source_label == "prototype_normalized_prior"
        assert parameter.source.reference == PAPER_ID


def test_sunitinib_paper_pathway_edges_preserve_paper_provenance() -> None:
    graph = _compose_demo_graph()

    assert graph.metadata.drug_state == StateId("ActiveExposure")
    assert graph.metadata.endpoint_states == (StateId("TumorVolume"),)
    assert len(graph.structural_edges()) == 4

    for node in graph.nodes:
        assert node.metadata.extension["paper_id"] == PAPER_ID
        assert node.metadata.extension["source_record_ids"]
        assert node.metadata.extension["evidence_anchor_ids"]

    for edge in graph.structural_edges():
        assert edge.evidence
        assert all(item.source_label == PAPER_ID for item in edge.evidence)
        extension = edge.metadata.extension
        assert extension["paper_id"] == PAPER_ID
        assert extension["curated_edge_id"]
        assert extension["source_record_ids"]
        assert extension["evidence_anchor_ids"]


def test_sunitinib_paper_pathway_compiles_to_executable_ir_without_duplicate_logic_checks() -> None:
    pathway = load_pathway(PATHWAY_ID)
    graph = _compose_demo_graph()
    compiled = compile_graph(graph, pathway)

    assert set(compiled.states) == RUNTIME_STATES
    assert compiled.metadata.pathway_id == PATHWAY_ID
    assert compiled.metadata.selected_configuration == CONFIGURATION
    assert compiled.metadata.drug_state == StateId("ActiveExposure")
    assert compiled.metadata.endpoint_states == (StateId("TumorVolume"),)
    assert compiled.metadata.expressions_execute_directly is True
    assert not [warning for warning in compiled.warnings if warning.severity == "error"]
    assert not any(isinstance(term.expression, DisplayExpression) for term in compiled.terms)
    assert not any(isinstance(equation.expression, DisplayExpression) for equation in compiled.equations)

    logic_ids = [str(item["id"]) for item in compiled.metadata.logic_checks]
    assert logic_ids == [
        "svegfr2_suppressed_by_active_exposure",
        "tumor_growth_rate_suppressed_after_svegfr2_delta",
    ]


def test_sunitinib_paper_pathway_simulates_expected_pd_directionality() -> None:
    compiled = compile_graph(_compose_demo_graph())
    result = simulate(SimulationInput(model=compiled, settings=SimulationSettings(t_end=48, n_points=97)))
    summaries = {summary.state: summary for summary in result.summaries}
    logic = {item.id: item for item in result.biological_logic}

    assert all(math.isfinite(value) and value >= 0.0 for series in result.series for value in series.values)
    assert summaries[StateId("sVEGFR2")].max_drop_fraction_from_baseline is not None
    assert summaries[StateId("sVEGFR2")].max_drop_fraction_from_baseline > 0.05
    assert summaries[StateId("TumorGrowthRate")].max_drop_fraction_from_baseline is not None
    assert summaries[StateId("TumorGrowthRate")].max_drop_fraction_from_baseline > 0.03
    assert summaries[StateId("TumorVolume")].final_fraction_change_from_baseline is not None
    assert summaries[StateId("TumorVolume")].final_fraction_change_from_baseline < 0.0
    assert len(result.biological_logic) == 2
    assert set(logic) == {
        "svegfr2_suppressed_by_active_exposure",
        "tumor_growth_rate_suppressed_after_svegfr2_delta",
    }
    assert all(item.result is True for item in logic.values())
