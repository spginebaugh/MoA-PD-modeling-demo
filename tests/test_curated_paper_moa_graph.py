from __future__ import annotations

import json

from services.annotation_import.curated_graph_builder import build_curated_paper_moa_graph
from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import ROOT, load_annotation_bundle
from services.annotation_import.models import CuratedPaperMoaGraph
from services.annotation_import.validation import validate_curated_paper_moa_graph


def _curated_graph(paper_id: str) -> CuratedPaperMoaGraph:
    evidence_graph = build_paper_evidence_graph(load_annotation_bundle(paper_id))
    return build_curated_paper_moa_graph(evidence_graph)


def test_sunitinib_curated_graph_prioritizes_causal_moa_chain() -> None:
    graph = _curated_graph("PMC5131886")

    assert graph.graph_kind == "curated_moa"
    assert graph.executable is False
    assert not validate_curated_paper_moa_graph(graph)
    assert not any(warning.code == "curated_source_record_missing" for warning in graph.warnings)

    assert {node.node_id for node in graph.nodes} == {
        "sunitinib_dose",
        "pk_model_structure",
        "pk_equation_variables",
        "plasma_compartment",
        "tumor_compartment",
        "sunitinib_plasma",
        "su12662_plasma",
        "active_unbound_concentration",
        "svegfr2_production",
        "svegfr2_biomarker",
        "svegfr2_endpoint_family",
        "delta_svegfr2",
        "tumor_growth_rate",
        "tumor_volume",
        "tumor_volume_endpoint_family",
        "ttp_hazard",
        "ttp_probability",
    }
    assert all(node.evidence_anchor_ids for node in graph.nodes)
    assert all(node.provenance for node in graph.nodes)
    assert all(node.context.species == "human" for node in graph.nodes)
    assert all(node.context.translation_stage == "clinical" for node in graph.nodes)

    edge_by_id = {edge.edge_id: edge for edge in graph.edges}
    assert (
        edge_by_id["curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production"].source,
        edge_by_id["curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production"].target,
        edge_by_id["curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production"].relation,
    ) == ("active_unbound_concentration", "svegfr2_production", "inhibits")
    assert edge_by_id["curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production"].causal_role == (
        "exposure_to_biomarker_production"
    )
    assert (
        edge_by_id["curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate"].source,
        edge_by_id["curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate"].target,
    ) == ("delta_svegfr2", "tumor_growth_rate")
    assert (
        edge_by_id["curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard"].source,
        edge_by_id["curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard"].target,
    ) == ("delta_svegfr2", "ttp_hazard")
    assert (
        edge_by_id["curated_edge:PMC5131886:ttp_hazard_drives_ttp_probability"].source,
        edge_by_id["curated_edge:PMC5131886:ttp_hazard_drives_ttp_probability"].target,
    ) == ("ttp_hazard", "ttp_probability")

    assert all(edge.evidence_anchor_ids for edge in graph.edges)
    assert all(edge.provenance for edge in graph.edges)
    assert all(edge.context.species == "human" for edge in graph.edges)
    assert all(edge.context.translation_stage == "clinical" for edge in graph.edges)
    assert edge_by_id["curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate"].context.state == (
        "baseline, treated"
    )


def test_sunitinib_curated_graph_binds_pk_pd_parameters_and_equations_to_targets() -> None:
    graph = _curated_graph("PMC5131886")
    parameters = {parameter.parameter_id: parameter for parameter in graph.parameters}
    equations = {equation.equation_id: equation for equation in graph.equations}

    assert parameters["curated_parameter:PMC5131886:dose_50_mg_daily"].target_node_id == "sunitinib_dose"
    assert parameters["curated_parameter:PMC5131886:population_pk_model_structure"].target_node_id == (
        "pk_model_structure"
    )
    assert parameters["curated_parameter:PMC5131886:pk_variable_cl"].target_node_id == (
        "pk_equation_variables"
    )
    assert parameters["curated_parameter:PMC5131886:pk_variable_k10"].target_node_id == (
        "pk_equation_variables"
    )
    assert parameters["curated_parameter:PMC5131886:sunitinib_plasma_endpoint"].target_node_id == (
        "sunitinib_plasma"
    )
    assert parameters["curated_parameter:PMC5131886:sunitinib_observed_plasma_endpoint"].target_node_id == (
        "sunitinib_plasma"
    )
    assert (
        parameters["curated_parameter:PMC5131886:su12662_plasma_endpoint"].target_node_id == "su12662_plasma"
    )
    assert parameters["curated_parameter:PMC5131886:su12662_predicted_plasma_endpoint"].target_node_id == (
        "su12662_plasma"
    )
    assert parameters["curated_parameter:PMC5131886:svegfr2_observed_endpoint"].target_node_id == (
        "svegfr2_endpoint_family"
    )
    assert parameters["curated_parameter:PMC5131886:tumor_volume_observed_endpoint"].target_node_id == (
        "tumor_volume_endpoint_family"
    )
    assert parameters["curated_parameter:PMC5131886:svegfr2_baseline_r0"].target_node_id == "delta_svegfr2"
    assert parameters["curated_parameter:PMC5131886:tgi_ic50"].target_edge_id == (
        "curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate"
    )
    assert parameters["curated_parameter:PMC5131886:slope_hazard_delta_auc_svegfr2"].target_edge_id == (
        "curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard"
    )
    assert parameters["curated_parameter:PMC5131886:hazard_variable_auc"].target_node_id == "ttp_hazard"
    assert all(parameter.review_status == "review_only" for parameter in graph.parameters)
    assert all(parameter.evidence_anchor_ids for parameter in graph.parameters)
    assert all(parameter.provenance for parameter in graph.parameters)
    assert all(parameter.context.species == "human" for parameter in graph.parameters)
    assert all(parameter.context.translation_stage == "clinical" for parameter in graph.parameters)

    assert equations["curated_equation:PMC5131886:active_unbound_concentration"].target_node_id == (
        "active_unbound_concentration"
    )
    assert equations["curated_equation:PMC5131886:svegfr2_indirect_response"].target_edge_id == (
        "curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production"
    )
    assert equations["curated_equation:PMC5131886:tgi_growth_rate_effect"].target_edge_id == (
        "curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate"
    )
    assert equations["eq:PMC5131886:ece40d8b730a6d9b"].target_node_id == "ttp_hazard"
    assert equations["eq:PMC5131886:f40c3d716a3c69c2"].target_node_id == "sunitinib_plasma"
    assert equations["eq:PMC5131886:4d9cbb929eb262d6"].target_node_id == "sunitinib_plasma"
    assert all(equation.evidence_anchor_ids for equation in graph.equations)
    assert all(equation.provenance for equation in graph.equations)
    assert all(equation.context.species == "human" for equation in graph.equations)
    assert all(equation.context.translation_stage == "clinical" for equation in graph.equations)
    assert "malformed_equation_text_needs_manual_review" in equations[
        "eq:PMC5131886:f40c3d716a3c69c2"
    ].warnings


def test_erlotinib_curated_graph_is_overlay_not_causal_moa_promotion() -> None:
    graph = _curated_graph("PMC3693219")

    assert graph.graph_kind == "overlay"
    assert graph.executable is False
    assert not graph.edges
    assert not validate_curated_paper_moa_graph(graph)
    assert not any(warning.code == "curated_source_record_missing" for warning in graph.warnings)
    assert {node.node_id for node in graph.nodes}.issuperset(
        {
            "erlotinib_exposure",
            "dosing_schedule",
            "resistance_probability",
            "resistant_population",
            "sensitive_population",
            "egfr_mutant_lung_cancer_context",
            "smoker_exposure_context",
            "nonsmoker_exposure_context",
            "high_dose_pulse_schedule",
            "withdrawal_schedule",
            "erlotinib_cmax_endpoint",
            "erlotinib_half_life",
            "erlotinib_elimination_rate_constant",
        }
    )
    assert all(node.evidence_anchor_ids for node in graph.nodes)
    assert all(node.provenance for node in graph.nodes)
    assert all(node.context.species == "human" for node in graph.nodes)
    assert all(node.context.translation_stage == "clinical" for node in graph.nodes)

    parameters = {parameter.parameter_id: parameter for parameter in graph.parameters}
    assert parameters["curated_parameter:PMC3693219:half_life_18h"].target_node_id == (
        "erlotinib_half_life"
    )
    assert parameters["curated_parameter:PMC3693219:elim_k_smokers_150"].target_node_id == (
        "erlotinib_elimination_rate_constant"
    )
    assert parameters["curated_parameter:PMC3693219:hamilton_cmax_endpoint"].target_node_id == (
        "erlotinib_cmax_endpoint"
    )
    assert parameters["curated_parameter:PMC3693219:smoker_150_plasma_endpoint"].target_node_id == (
        "smoker_exposure_context"
    )
    assert parameters["curated_parameter:PMC3693219:pulse_probability_resistance_endpoint"].target_node_id == (
        "resistance_probability"
    )
    assert all(parameter.review_status == "review_only" for parameter in graph.parameters)
    assert all(parameter.evidence_anchor_ids for parameter in graph.parameters)
    assert all(parameter.provenance for parameter in graph.parameters)
    assert all(parameter.context.species == "human" for parameter in graph.parameters)
    assert all(parameter.context.translation_stage == "clinical" for parameter in graph.parameters)
    assert {missing.name: missing.severity for missing in graph.missing_inputs}[
        "pk_exposure_parameters"
    ] == "error"


def test_generated_curated_graph_artifacts_are_schema_valid() -> None:
    for paper_id in ("PMC3693219", "PMC5131886"):
        output_path = ROOT / "data" / "curated_annotation_graphs" / f"{paper_id}.curated_moa_graph.json"
        parsed = CuratedPaperMoaGraph.model_validate_json(output_path.read_text())

        assert parsed.paper_id == paper_id
        assert parsed.executable is False
        assert not validate_curated_paper_moa_graph(parsed)


def test_combined_paper_moa_graph_artifact_summarizes_required_evidence() -> None:
    output_path = ROOT / "data" / "curated_annotation_graphs" / "combined.paper_moa_graph.json"
    parsed = CuratedPaperMoaGraph.model_validate_json(
        (ROOT / "data" / "curated_annotation_graphs" / "PMC5131886.curated_moa_graph.json").read_text()
    )
    data = json.loads(output_path.read_text())

    assert parsed.paper_id == "PMC5131886"
    assert data["paper_ids"] == ["PMC3693219", "PMC5131886"]
    assert data["runtime_executable"] is False
    assert data["summary"]["parameter_count"] == 50
    assert data["summary"]["causal_edge_count"] == 10
    assert data["summary"]["equation_count"] == 7
    assert data["summary"]["provenance_record_count"] == 88
    assert data["causal_prioritization"]["PMC3693219"]["causal_edge_count"] == 0
    assert data["causal_prioritization"]["PMC5131886"]["candidate_edge_count"] == 6

    assert set(data["tables"]) >= {
        "causal_edges",
        "parameters",
        "equations",
        "contexts",
        "provenance",
    }
    assert all(row["evidence_anchor_ids"] for row in data["tables"]["parameters"])
    assert all(row["provenance_count"] > 0 for row in data["tables"]["parameters"])
    assert all(row["species"] for row in data["tables"]["contexts"])
    assert all(row["translation_stage"] for row in data["tables"]["contexts"])

    summary_path = ROOT / "docs" / "paper-annotation-moa-graph-summary.md"
    summary = summary_path.read_text()
    assert "Context And State" in summary
    assert "Provenance Coverage" in summary
