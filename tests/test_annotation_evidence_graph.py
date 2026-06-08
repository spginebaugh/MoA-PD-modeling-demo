from __future__ import annotations

from collections import Counter

from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import load_annotation_bundle
from services.annotation_import.models import PaperEvidenceGraph
from services.annotation_import.validation import validate_evidence_graph


def _link_counts(graph: PaperEvidenceGraph) -> Counter[str]:
    return Counter(link.relation for link in graph.links)


def test_pmc3693219_ignores_projection_mechanisms_and_keeps_simulation_endpoints() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC3693219"))

    assert len(graph.edges) == 0
    assert graph.summary["top_level_mechanism_step_count"] == 0
    assert graph.summary["kg_projection_mechanism_node_count"] == 2
    assert graph.summary["kg_projection_verification_node_count"] == 3
    assert {warning.code for warning in graph.warnings}.issuperset(
        {
            "kg_projection_mechanisms_ignored",
            "kg_projection_verifications_ignored",
            "no_top_level_mechanism_chains",
        }
    )
    assert len(graph.simulation_parameters) == 154
    assert graph.summary["figure_annotation_count"] == 6
    assert graph.summary["study_design_count"] == 14
    assert graph.summary["scientific_symbol_count"] == 13
    link_counts = _link_counts(graph)
    assert link_counts["simulation_parameter_for"] == 154
    assert link_counts["derived_from_figure"] > 0
    assert graph.summary["simulation_parameter_role_counts"] == {
        "calibration_or_validation_endpoint": 121,
        "candidate_model_input": 17,
        "model_input": 4,
        "review_only_candidate_input": 12,
    }
    assert not validate_evidence_graph(graph)


def test_pmc5131886_builds_four_top_level_mechanism_step_edges() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC5131886"))

    assert len(graph.edges) == 4
    assert graph.summary["top_level_mechanism_chain_count"] == 3
    assert graph.summary["top_level_mechanism_step_count"] == 4
    assert graph.summary["top_level_mechanism_verification_count"] == 4
    assert graph.summary["kg_projection_mechanism_node_count"] == 5
    assert graph.summary["kg_projection_verification_node_count"] == 10
    assert {edge.source_record_id for edge in graph.edges} == {
        "step:PMC5131886:05f1ecda4b6b0995",
        "step:PMC5131886:900e7cc08f84c890",
        "step:PMC5131886:27fa15d47ecb84da",
        "step:PMC5131886:d0ac7603ff3f2325",
    }
    assert {edge.verification_verdict for edge in graph.edges} == {
        "verified_therapeutic_moa",
        "paper_supported_only",
        "model_derived_pd_relation",
    }
    assert all(edge.source_record_type == "mechanism_step" for edge in graph.edges)
    assert all(edge.evidence_anchor_ids for edge in graph.edges)
    assert graph.summary["figure_annotation_count"] == 3
    assert graph.summary["study_design_count"] == 8
    assert graph.summary["scientific_symbol_count"] == 7
    link_counts = _link_counts(graph)
    assert link_counts["parameter_for"] == len(graph.parameters)
    assert link_counts["simulation_parameter_for"] == len(graph.simulation_parameters)
    assert link_counts["equation_defines"] == len(graph.equations)
    assert link_counts["variable_in_equation"] > 0
    assert not validate_evidence_graph(graph)


def test_context_term_matching_does_not_match_rat_inside_concentration_or_rate() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC5131886"))
    by_step = {edge.source_record_id: edge for edge in graph.edges}

    assert by_step["step:PMC5131886:05f1ecda4b6b0995"].context.species == "human"
    assert all(edge.context.species != "rat" for edge in graph.edges)


def test_verification_join_uses_exact_chain_and_step_ids() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC5131886"))
    by_step = {edge.source_record_id: edge for edge in graph.edges}

    assert by_step["step:PMC5131886:05f1ecda4b6b0995"].verification_id == (
        "moa_verification:PMC5131886:60eaa642dfb3f4a7"
    )
    assert by_step["step:PMC5131886:900e7cc08f84c890"].verification_id == (
        "moa_verification:PMC5131886:d0e48dbf693cac3a"
    )
    assert by_step["step:PMC5131886:27fa15d47ecb84da"].verification_id == (
        "moa_verification:PMC5131886:0ba94e62eba8ab2a"
    )
    assert by_step["step:PMC5131886:d0ac7603ff3f2325"].verification_id == (
        "moa_verification:PMC5131886:70fae200d0e1a6ad"
    )


def test_missing_units_and_uncurated_equations_stay_review_only_or_display_only() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC5131886"))

    missing_unit_parameters = [parameter for parameter in graph.parameters if parameter.unit is None]
    missing_unit_simulation_parameters = [
        parameter for parameter in graph.simulation_parameters if parameter.unit is None
    ]

    assert missing_unit_parameters
    assert missing_unit_simulation_parameters
    assert all(parameter.review_status == "review_only" for parameter in missing_unit_parameters)
    assert all(parameter.review_status == "review_only" for parameter in missing_unit_simulation_parameters)
    assert len(graph.equations) == 5
    assert all(equation.metadata["display_only"] is True for equation in graph.equations)
    assert all(equation.metadata["executable"] is False for equation in graph.equations)


def test_provided_entity_normalization_is_consumed_without_free_form_renormalization() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC5131886"))

    sunitinib = next(node for node in graph.nodes if node.node_id == "ChEMBL:CHEMBL535")
    vegfr2 = next(node for node in graph.nodes if node.node_id == "UniProt:P35968")

    assert sunitinib.label == "sunitinib"
    assert sunitinib.metadata["match_score"] == 0.96
    assert vegfr2.label == "VEGFR2"
    assert vegfr2.metadata["match_score"] == 0.96
