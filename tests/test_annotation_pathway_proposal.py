from __future__ import annotations

from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import ROOT, load_annotation_bundle
from services.annotation_import.models import AnnotationProposalRule
from services.annotation_import.pathway_patch import build_pathway_proposal
from services.annotation_import.rules import load_proposal_rule
from services.annotation_import.validation import validate_pathway_proposal
from services.pathway.loader import list_pathways


def test_erlotinib_bundle_generates_review_only_egfr_overlay_proposal() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC3693219"))
    rule = load_proposal_rule("PMC3693219")
    assert rule is not None

    proposal = build_pathway_proposal(graph)

    assert proposal.proposal_kind == "overlay"
    assert proposal.target_pathway_id == rule.target_pathway_id
    assert proposal.proposed_pathway_id is None
    assert proposal.curated_graph_id == "curated:PMC3693219:erlotinib_resistance_overlay"
    assert proposal.executable is False
    assert not proposal.proposed_edges
    assert {node.node_id for node in proposal.proposed_nodes}.issuperset(
        {overlay_rule.node_id for overlay_rule in rule.overlay_nodes}
    )
    assert "egfr_mutant_lung_cancer_context" in {node.node_id for node in proposal.proposed_nodes}
    assert all(node.evidence_anchor_ids for node in proposal.proposed_nodes)
    assert all(node.provenance is not None for node in proposal.proposed_nodes)
    assert proposal.required_missing_inputs
    assert not any(
        warning.code == "curated_source_record_missing" for warning in proposal.provenance_warnings
    )
    assert not validate_pathway_proposal(proposal)


def test_overlay_behavior_requires_data_owned_proposal_rule() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC3693219"))

    proposal = build_pathway_proposal(
        graph,
        AnnotationProposalRule(paper_id="PMC3693219", proposal_kind="evidence_only"),
    )

    assert proposal.proposal_kind == "evidence_only"
    assert proposal.target_pathway_id is None
    assert proposal.proposed_pathway_id is None
    assert not proposal.proposed_nodes


def test_sunitinib_bundle_generates_separate_review_only_pathway_proposal() -> None:
    graph = build_paper_evidence_graph(load_annotation_bundle("PMC5131886"))
    rule = load_proposal_rule("PMC5131886")
    assert rule is not None

    proposal = build_pathway_proposal(graph)

    assert proposal.proposal_kind == "new_pathway"
    assert proposal.target_pathway_id is None
    assert proposal.proposed_pathway_id == rule.proposed_pathway_id
    assert proposal.curated_graph_id == "curated:PMC5131886:sunitinib_vegfr2_hcc_moa"
    assert proposal.executable is False
    assert len(proposal.proposed_nodes) == 17
    assert len(proposal.proposed_edges) == 10
    assert {edge.verification_verdict for edge in proposal.proposed_edges} == {None}
    assert "curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard" in {
        edge.edge_id for edge in proposal.proposed_edges
    }
    assert all(edge.evidence_anchor_ids for edge in proposal.proposed_edges)
    assert all(edge.provenance is not None for edge in proposal.proposed_edges)
    assert {
        "curated_parameter:PMC5131886:population_pk_model_structure",
        "curated_parameter:PMC5131886:pk_variable_cl",
        "curated_parameter:PMC5131886:pk_variable_k10",
        "curated_parameter:PMC5131886:sunitinib_observed_plasma_endpoint",
        "curated_parameter:PMC5131886:su12662_predicted_plasma_endpoint",
        "curated_parameter:PMC5131886:svegfr2_observed_endpoint",
        "curated_parameter:PMC5131886:tumor_volume_observed_endpoint",
        "curated_parameter:PMC5131886:hazard_variable_auc",
    }.issubset({parameter.parameter_id for parameter in proposal.proposed_parameters})
    assert len(proposal.proposed_parameters) == 30
    assert len(proposal.proposed_equations) == 7
    assert all(equation.evidence_anchor_ids for equation in proposal.proposed_equations)
    assert all(equation.provenance is not None for equation in proposal.proposed_equations)
    assert all(equation.metadata["executable"] is False for equation in proposal.proposed_equations)
    assert not validate_pathway_proposal(proposal)


def test_pathway_proposals_are_not_runtime_pathways() -> None:
    runtime_pathway_ids = {summary.pathway_id for summary in list_pathways()}

    assert runtime_pathway_ids == {"egfr_erbb_demo"}
    assert not (ROOT / "data" / "pathways" / "PMC3693219.overlay.proposal.json").exists()
    assert not (ROOT / "data" / "pathways" / "PMC5131886.new_pathway.proposal.json").exists()


def test_annotation_import_production_code_has_no_paper_specific_pathway_rules() -> None:
    forbidden_terms = (
        "egfr_erbb_demo",
        "erlotinib",
        "sunitinib",
        "hepatocellular",
        "egfr-mutant",
        "egfr mutant",
        "sunitinib_vegfr2_hcc_demo",
        "resistant_population",
        "sensitive_population",
    )
    production_files = (
        ROOT / "services" / "annotation_import" / "pathway_patch.py",
        ROOT / "services" / "annotation_import" / "provenance.py",
    )

    for path in production_files:
        source = path.read_text().lower()
        assert not any(term in source for term in forbidden_terms)
